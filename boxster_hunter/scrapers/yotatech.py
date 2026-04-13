"""YotaTech 'Vehicles - Trailers (Complete)' classifieds scraper.

YotaTech runs vBulletin (same engine as 986forum, Rennlist, AudiWorld's old
marketplace) and exposes the same ``thread_title_{tid}`` anchors. The f108
subforum is for complete-vehicle for-sale listings only — Tacomas, Tundras,
Land Cruisers, 4Runners, etc. The orchestrator's per-target title-keyword
filter handles routing (only 4Runner-mentioning threads count for our 4Runner
target).

robots.txt allows scraping with no AI-specific blocks. Crawl-delay is 1 sec
which matches BaseScraper's default.
"""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import extract_first_post_body, parse_vbulletin
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.yotatech.com/forums/f108/"
BASE_URL = "https://www.yotatech.com"
POST_BODY_SELECTOR = 'div[id^="post_message_"]'


class YotaTechScraper(BaseScraper):
    source = "yotatech"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_vbulletin(payload, self.source, BASE_URL, self.now)

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
