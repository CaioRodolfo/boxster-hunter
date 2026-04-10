"""Craigslist scraper. Pulls from RSS feeds in the cities within driving range."""

from __future__ import annotations

import feedparser

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

# Cities within ~4 hours of Wilmington, DE per the spec.
CRAIGSLIST_CITIES = [
    "philadelphia",
    "newyork",
    "baltimore",
    "washingtondc",
    "boston",
    "pittsburgh",
]

# Craigslist supports `format=rss` for any search URL.
FEED_URL_TEMPLATE = (
    "https://{city}.craigslist.org/search/cta?query=porsche+boxster+s&srchType=T&format=rss"
)


class CraigslistScraper(BaseScraper):
    source = "craigslist"

    def __init__(self, cities: list[str] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cities = cities or CRAIGSLIST_CITIES

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        for city in self.cities:
            url = FEED_URL_TEMPLATE.format(city=city)
            try:
                resp = self.http_get(url)
                resp.raise_for_status()
            except Exception:
                self.log.warning("craigslist fetch failed for %s", city, exc_info=True)
                continue
            listings.extend(self.parse(resp.text, city=city))
        return listings

    def parse(self, payload: str | bytes, city: str | None = None) -> list[Listing]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")
        feed = feedparser.parse(payload)
        listings: list[Listing] = []
        for entry in feed.entries:
            url = entry.get("link") or entry.get("id")
            if not url:
                continue
            title = entry.get("title", "")
            description = entry.get("summary", "") or entry.get("description", "")
            source_id = url.rstrip("/").split("/")[-1].split(".")[0]
            listings.append(
                Listing(
                    source=self.source,
                    source_id=source_id,
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=title,
                    description=description,
                    year=_first_year(title),
                    location=city,
                )
            )
        return listings


def _first_year(text: str) -> int | None:
    import re

    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None
