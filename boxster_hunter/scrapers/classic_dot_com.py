"""Classic.com scraper.

Classic.com is a Phoenix LiveView app rendering listings as Tailwind cards
with no semantic class names. The stable hooks are:

  * Each card has an anchor `<h3><a href="/veh/{slug}">Title</a></h3>`
  * Each card has a price block `<div id="vehicle-listing-{N}-price">`
  * Each card has structured spec rows containing mileage and transmission
    next to a `<img alt="...">` icon

We anchor on the price div (one per listing, unique id), then walk up to the
nearest ancestor card and extract title/mileage/price/location from there.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.classic.com/m/porsche/boxster/986/s-manual/"

_VEH_HREF = re.compile(r"^/veh/[^/]+$")
_PRICE_ID = re.compile(r"^vehicle-listing-(\d+)-price$")
_LISTING_ID = re.compile(r"^vehicle-listing-(\d+)$")


class ClassicDotComScraper(BaseScraper):
    source = "classic.com"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        soup = BeautifulSoup(payload, "lxml")

        # Each listing's price div appears twice (mobile + table layouts).
        # Dedupe by listing id.
        price_divs = soup.find_all("div", id=_PRICE_ID)
        seen_ids: set[str] = set()
        out: list[Listing] = []
        for price_div in price_divs:
            m = _PRICE_ID.match(price_div.get("id", ""))
            if not m:
                continue
            listing_id = m.group(1)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            card = _find_card_root(price_div)
            if card is None:
                continue

            link = card.find("a", href=_VEH_HREF)
            if link is None:
                continue
            href = link["href"]
            url = f"https://www.classic.com{href}"

            title_node = card.find("h3")
            title = title_node.get_text(strip=True) if title_node else link.get_text(strip=True)

            price = _to_int(price_div.get_text(" ", strip=True))
            mileage = _extract_mileage(card)
            location = _extract_location(card)
            year = _first_year(title)

            out.append(
                Listing(
                    source=self.source,
                    source_id=listing_id,
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=title,
                    description=title,  # No long description on the search page
                    year=year,
                    price=price,
                    mileage=mileage,
                    location=location,
                )
            )
        return out


def _find_card_root(price_div: Tag) -> Tag | None:
    """Walk up until we hit an ancestor that contains the title <h3>."""
    node = price_div
    for _ in range(8):
        node = node.parent
        if node is None:
            return None
        if node.find("h3"):
            return node
    return None


_MILEAGE_RE = re.compile(r"(\d[\d,]*)\s*(?:k\s*)?mi", re.IGNORECASE)


def _extract_mileage(card: Tag) -> int | None:
    """Mileage shows as either '110k mi' or '6,865 mi'."""
    text = card.get_text(" ", strip=True)
    m = _MILEAGE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    if "k" in m.group(0).lower():
        return int(raw) * 1000
    try:
        return int(raw)
    except ValueError:
        return None


def _extract_location(card: Tag) -> str | None:
    """Location is rendered next to a flag image with alt-less img + text."""
    for div in card.find_all("div"):
        text = div.get_text(" ", strip=True)
        # City, ST, USA — typical Classic.com format
        if "USA" in text and "," in text and len(text) < 80:
            return text
    return None


def _to_int(text: str) -> int | None:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else None


def _first_year(text: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None
