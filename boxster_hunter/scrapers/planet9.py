"""Planet-9 'Porsche Cars Classifieds' subforum scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import extract_first_post_body, parse_xenforo
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.planet-9.com/forums/porsche-cars-classifieds.69/"
BASE_URL = "https://www.planet-9.com"
POST_BODY_SELECTOR = "div.bbWrapper"


class Planet9Scraper(BaseScraper):
    source = "planet9"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_xenforo(payload, self.source, BASE_URL, self.now)

    def enrich_description(self, listing: Listing) -> bool:
        try:
            resp = self.http_get(listing.url_str)
            resp.raise_for_status()
        except Exception:
            self.log.warning("enrich failed for %s", listing.url_str, exc_info=True)
            return False
        body = extract_first_post_body(resp.text, POST_BODY_SELECTOR)
        if not body:
            return False
        listing.description = body[:8000]
        return True
