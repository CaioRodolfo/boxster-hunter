"""986forum.com 'For Sale' subforum scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import CardSelectors, parse_cards
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://986forum.com/forums/986-boxster-s-for-sale/"

SELECTORS = CardSelectors(
    card="li.thread, tr.thread, div.thread-row",
    link="a.thread-title, a.title, a[href]",
    title="a.thread-title, a.title",
    description=".thread-snippet, .snippet, .post-preview",
    location=".thread-location, .location",
    base_url="https://986forum.com",
)


class BoxsterForumScraper(BaseScraper):
    source = "986forum"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_cards(payload, SELECTORS, self.source, self.now)
