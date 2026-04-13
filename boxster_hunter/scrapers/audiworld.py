"""AudiWorld marketplace scraper.

AudiWorld migrated their marketplace to a custom listing UI in 2025. Each
``.shelf-item`` div embeds a ``<script type="application/ld+json">`` block
with a schema.org Car object — the cleanest possible source. We pull every
field straight from JSON-LD (name, year, model, brand, VIN, transmission,
engine, price, location, description, URL) instead of scraping HTML.

If a future redesign moves the JSON-LD elsewhere, the parser falls back to
None on the affected listing rather than crashing.

robots.txt allows the marketplace path; the rate limit is 1 req/sec which
matches BaseScraper's default.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.audiworld.com/forums/market/"
BASE_URL = "https://www.audiworld.com"

_THREAD_TID_RE = re.compile(r"/market/(\d+)")


class AudiWorldScraper(BaseScraper):
    source = "audiworld"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        soup = BeautifulSoup(payload, "lxml")
        out: list[Listing] = []
        seen_tids: set[str] = set()

        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Only Car schema entries — AudiWorld puts other JSON-LD blobs on
            # the page (BreadcrumbList, ItemList, etc.) that we don't care about.
            if data.get("@type") != "Car":
                continue

            url = data.get("url", "")
            tid_match = _THREAD_TID_RE.search(url)
            if not tid_match:
                continue
            tid = tid_match.group(1)
            if tid in seen_tids:
                continue
            seen_tids.add(tid)

            offer = _first_offer(data)
            seller_address = _seller_address(offer)
            location = _format_location(seller_address)
            engine = (data.get("vehicleEngine") or {}).get("name")

            out.append(
                Listing(
                    source=self.source,
                    source_id=tid,
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=data.get("name", ""),
                    description=data.get("description", ""),
                    year=_parse_year(data.get("modelDate")),
                    model=data.get("model"),
                    transmission=data.get("vehicleTransmission"),
                    vin=data.get("vehicleIdentificationNumber"),
                    engine=engine,
                    price=_parse_price(offer),
                    location=location,
                    image_urls=[data["image"]] if data.get("image") else [],
                )
            )
        return out

    def enrich_description(self, listing: Listing) -> bool:
        """Follow the listing link and grab the full OP body if the JSON-LD
        description was truncated. The OP lives under ``div#posts``.
        """
        if listing.description and len(listing.description) > 500:
            return False
        try:
            resp = self.http_get(listing.url_str, allow_redirects=True)
            resp.raise_for_status()
        except Exception:
            self.log.warning("enrich failed for %s", listing.url_str, exc_info=True)
            return False

        soup = BeautifulSoup(resp.content, "lxml")
        op = soup.find("div", id="posts")
        if op is None:
            return False
        text = op.get_text(" ", strip=True)
        if not text:
            return False
        listing.description = text[:8000]
        return True


def _first_offer(data: dict[str, Any]) -> dict[str, Any]:
    offers = data.get("offers", [])
    if isinstance(offers, list) and offers:
        return offers[0]
    if isinstance(offers, dict):
        return offers
    return {}


def _seller_address(offer: dict[str, Any]) -> dict[str, Any]:
    seller = offer.get("seller") or {}
    return seller.get("address") or {}


def _format_location(addr: dict[str, Any]) -> str | None:
    city = addr.get("addressLocality")
    region = addr.get("addressRegion")
    if city and region:
        return f"{city}, {region}"
    return city or region or None


def _parse_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_price(offer: dict[str, Any]) -> int | None:
    price = offer.get("price")
    if price is None:
        return None
    try:
        return int(float(price))
    except (ValueError, TypeError):
        return None
