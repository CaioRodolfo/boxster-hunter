"""Cars & Bids scraper.

Cars & Bids is a pure React SPA — there's no SSR data we can scrape from the
HTML. They do publish an RSS feed of every active auction, which is exactly
what we need: title + canonical URL + a long-form description full of details
the scoring engine can chew on.

The RSS contains every active auction across all makes (~200 at any given
time), so we filter to "boxster" mentions in the parser. Year + 6-speed +
IMS detection happens later in the scoring engine.
"""

from __future__ import annotations

import feedparser

from boxster_hunter.models import Listing
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
            # Cars & Bids has all makes — keep only Boxster mentions and let
            # the scoring engine handle the rest of the spec match.
            if "boxster" not in title.lower():
                continue
            url = entry.get("link") or entry.get("id")
            if not url:
                continue
            description = _strip_html(entry.get("summary", "") or entry.get("description", ""))
            year = _first_year(title)
            out.append(
                Listing(
                    source=self.source,
                    source_id=_source_id_from_url(url),
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=title,
                    description=description,
                    year=year,
                    price_is_auction=True,
                )
            )
        return out


def _strip_html(s: str) -> str:
    """RSS descriptions are HTML; pull the text out for the scoring engine."""
    if not s:
        return ""
    from bs4 import BeautifulSoup

    return BeautifulSoup(s, "lxml").get_text(" ", strip=True)


def _first_year(text: str) -> int | None:
    import re

    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def _source_id_from_url(url: str) -> str:
    """Cars & Bids URLs look like /auctions/{shortid}/{slug}."""
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] != "auctions":
        return parts[-2]  # the short id
    return parts[-1]
