"""Cars & Bids scraper. Their search endpoint returns JSON; parse directly."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://carsandbids.com/api/search?q=porsche+boxster+s+986"


class CarsAndBidsScraper(BaseScraper):
    source = "carsandbids"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        data = json.loads(payload)
        return [self._parse_one(item) for item in data.get("auctions", [])]

    def _parse_one(self, item: dict[str, Any]) -> Listing:
        slug = item.get("slug") or item.get("id", "")
        url = f"https://carsandbids.com/auctions/{slug}"
        return Listing(
            source=self.source,
            source_id=str(item.get("id") or slug),
            url=url,
            first_seen=self.now(),
            last_updated=self.now(),
            title=item.get("title", ""),
            description=item.get("description") or item.get("doc", ""),
            year=item.get("year"),
            model=item.get("model"),
            mileage=_to_int(item.get("mileage")),
            color_exterior=item.get("exteriorColor"),
            color_interior=item.get("interiorColor"),
            transmission=item.get("transmission"),
            vin=item.get("vin"),
            price=_to_int(item.get("currentBid") or item.get("highBid")),
            price_is_auction=True,
            auction_end=_parse_iso(item.get("endsAt")),
            location=item.get("location"),
            seller_type=item.get("sellerType"),
            image_urls=list(item.get("images", []) or []),
        )


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
