"""Bring a Trailer scraper.

BaT publishes a site-wide WordPress RSS feed at ``/feed/`` containing every
currently-live and recently-ended auction (~20 items, refreshed hourly per the
feed's ``sy:updatePeriod``). Each item has a rich HTML description with full
seller details — no detail-fetch enrichment needed.

**robots.txt compliance:** BaT's robots.txt has ``Disallow: /*/feed/`` which
blocks subcategory feeds like ``/porsche/boxster/feed/``, but the site-wide
``/feed/`` at the root is **not** disallowed (no segment before ``/feed/``).
BaT also sets ``Crawl-delay: 1`` which matches BaseScraper's default rate
limit, so we're well within their policy.
"""

from __future__ import annotations

import feedparser

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._rss_common import first_year, source_id_from_url, strip_html
from boxster_hunter.scrapers.base import BaseScraper

RSS_URL = "https://bringatrailer.com/feed/"


class BringATrailerScraper(BaseScraper):
    source = "bringatrailer"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(RSS_URL)
        resp.raise_for_status()
        return self.parse(resp.content)

    def parse(self, payload: str | bytes) -> list[Listing]:
        feed = feedparser.parse(payload)
        out: list[Listing] = []
        for entry in feed.entries:
            title = entry.get("title", "")
            # BaT's feed contains every make — keep only Boxster mentions and
            # let the scoring engine handle year/trans/IMS/color.
            if "boxster" not in title.lower():
                continue
            url = entry.get("link") or entry.get("id")
            if not url:
                continue
            description = strip_html(entry.get("summary", "") or entry.get("description", ""))
            out.append(
                Listing(
                    source=self.source,
                    source_id=source_id_from_url(url),
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=title,
                    description=description,
                    year=first_year(title),
                    price_is_auction=True,
                )
            )
        return out
