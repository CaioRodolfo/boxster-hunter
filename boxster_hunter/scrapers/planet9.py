"""Planet-9 'For Sale' subforum scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import CardSelectors, parse_cards
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.planet-9.com/threads/?prefix_id=1"

SELECTORS = CardSelectors(
    card="li.thread, tr.thread, div.structItem--thread",
    link="a.thread-title, a.structItem-title, a[href]",
    title="a.thread-title, a.structItem-title",
    description=".structItem-cell--main .structItem-resourceTagLine, .thread-snippet",
    location=".structItem-cell--meta .structItem-startDate, .thread-location",
    base_url="https://www.planet-9.com",
)


class Planet9Scraper(BaseScraper):
    source = "planet9"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_cards(payload, SELECTORS, self.source, self.now)
