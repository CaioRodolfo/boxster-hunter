"""Craigslist scraper — DROPPED.

The original spec called for parsing Craigslist via per-city RSS feeds. As of
2026, Craigslist actively blocks bots:

  * Their RSS endpoints (`?format=rss`) return HTTP 403 to non-residential IPs
    and any unauthenticated automated client. GitHub Actions runners and most
    cloud IPs are flat-out blocked.
  * The HTML search pages render results in JavaScript. The static `<noscript>`
    fallback only contains "see also" suggestions (random cars in the same
    category), not actual query matches — useless for our purpose.
  * Even when an HTML page does load, Craigslist rotates obfuscated CSS
    classes and may serve a captcha on automated patterns.

We're dropping Craigslist from the active source list. To re-enable it later
you'd need either (a) a residential proxy, (b) a headless browser with stealth
plugins, or (c) the user to manually run a search and feed the URL into a
one-off scraper. None of those are appropriate for a free hourly cron.

This module is kept as a stub so the rewrite is documented in code, but
``CraigslistScraper`` is no longer registered in ``main.ALL_SCRAPERS``.
"""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper


class CraigslistScraper(BaseScraper):
    source = "craigslist"

    def fetch_listings(self) -> list[Listing]:
        raise NotImplementedError(
            "Craigslist scraping is disabled — see module docstring for context."
        )

    def parse(self, payload: str | bytes) -> list[Listing]:
        return []
