"""986forum.com 'Boxsters/Cayman Cars - For Sale & Wanted' subforum scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import parse_vbulletin
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://986forum.com/forums/boxsters-cayman-cars-sale-wanted/"
BASE_URL = "https://986forum.com"


class BoxsterForumScraper(BaseScraper):
    source = "986forum"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_vbulletin(payload, self.source, BASE_URL, self.now)
