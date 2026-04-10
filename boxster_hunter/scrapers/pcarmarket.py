"""PCARMARKET scraper.

PCARMARKET exposes a clean public JSON API at /api/auctions/. We filter
server-side by ``make=porsche`` and let the scoring engine pick out 986
Boxster S matches from the results.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

API_URL = "https://www.pcarmarket.com/api/auctions/?make=porsche&limit=24"
LISTING_URL_TEMPLATE = "https://www.pcarmarket.com/auction/{slug}/"


class PCarMarketScraper(BaseScraper):
    source = "pcarmarket"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(API_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        results = data.get("results", [])
        return [self._parse_one(item) for item in results if _looks_like_boxster(item)]

    def _parse_one(self, item: dict[str, Any]) -> Listing:
        slug = item.get("slug", "")
        url = LISTING_URL_TEMPLATE.format(slug=slug)
        vehicle = item.get("vehicle", {}) or {}
        mileage = item.get("mileage_body")
        if mileage and item.get("odometer_type") == "km":
            mileage = int(mileage * 0.621371)  # km → mi
        elif mileage is not None:
            mileage = int(mileage)

        return Listing(
            source=self.source,
            source_id=str(item.get("id", slug)),
            url=url,
            first_seen=self.now(),
            last_updated=self.now(),
            title=item.get("title", ""),
            description=item.get("title", ""),
            year=vehicle.get("year"),
            model=vehicle.get("model"),
            mileage=mileage,
            price=_high_bid_to_int(item.get("high_bid")),
            price_is_auction=True,
            auction_end=_parse_iso(item.get("end_date")),
            location=item.get("location"),
            image_urls=[item["featured_image_large_url"]] if item.get("featured_image_large_url") else [],
        )


def _looks_like_boxster(item: dict[str, Any]) -> bool:
    """Filter the per-make API down to Boxsters specifically."""
    title = (item.get("title") or "").lower()
    model = ((item.get("vehicle") or {}).get("model") or "").lower()
    return "boxster" in title or "boxster" in model


def _high_bid_to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
