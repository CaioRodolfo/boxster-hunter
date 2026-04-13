"""Rennlist 'For Sale Ads (Member to Member)' subforum scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import extract_first_post_body, parse_vbulletin
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://rennlist.com/forums/for-sale-ads-member-to-member-fs-wtb-free-136/"
BASE_URL = "https://rennlist.com"
POST_BODY_SELECTOR = 'div[id^="post_message_"]'


class RennlistScraper(BaseScraper):
    source = "rennlist"

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
