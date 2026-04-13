"""Cars & Bids scraper.

Cars & Bids is a pure React SPA — there's no SSR data we can scrape from the
HTML. They publish an RSS feed of every current auction at /rss.xml, which is
exactly what we need: title + canonical URL + a long-form description full of
details the scoring engine can chew on.

The scraper returns *every* item in the feed regardless of make — the
orchestrator routes each listing to whichever target's title keyword matches
(currently Boxster and S3). A pure-Python keyword filter here would have to
know about every target; the orchestrator already does the routing centrally.
"""

from __future__ import annotations

import feedparser

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._rss_common import first_year, source_id_from_url, strip_html
from boxster_hunter.scrapers.base import BaseScraper

RSS_URL = "https://carsandbids.com/rss.xml"


class CarsAndBidsScraper(BaseScraper):
    source = "carsandbids"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(RSS_URL)
        resp.raise_for_status()
        return self.parse(resp.content)

    def parse(self, payload: str | bytes) -> list[Listing]:
        feed = feedparser.parse(payload)
        out: list[Listing] = []
        for entry in feed.entries:
            title = entry.get("title", "")
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
