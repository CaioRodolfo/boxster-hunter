"""Rennlist 986 Boxster classifieds scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import CardSelectors, parse_cards
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://rennlist.com/forums/986-forum/classifieds/"

SELECTORS = CardSelectors(
    card="li.thread, tr.thread, div.thread-row",
    link="a.thread-title, a.title, a[href]",
    title="a.thread-title, a.title",
    description=".thread-snippet, .snippet",
    location=".thread-location, .location",
    base_url="https://rennlist.com",
)


class RennlistScraper(BaseScraper):
    source = "rennlist"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_cards(payload, SELECTORS, self.source, self.now)
