"""Orchestrator. Wires scrapers → dedup → scoring → Notion → notifier.

Run modes:

  python -m boxster_hunter.main             # live run (uses env vars)
  python -m boxster_hunter.main --dry-run   # skip live HTTP from scrapers
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

from boxster_hunter.db import Database
from boxster_hunter.models import Listing
from boxster_hunter.notifier import Notifier
from boxster_hunter.notion_sink import NotionSink
from boxster_hunter.scoring import score_listing
from boxster_hunter.scrapers.base import BaseScraper
from boxster_hunter.scrapers.boxster_forum import BoxsterForumScraper
from boxster_hunter.scrapers.carsandbids import CarsAndBidsScraper
from boxster_hunter.scrapers.classic_dot_com import ClassicDotComScraper
from boxster_hunter.scrapers.craigslist import CraigslistScraper
from boxster_hunter.scrapers.pcarmarket import PCarMarketScraper
from boxster_hunter.scrapers.planet9 import Planet9Scraper
from boxster_hunter.scrapers.rennlist import RennlistScraper

log = logging.getLogger("boxster.main")

ALL_SCRAPERS: list[type[BaseScraper]] = [
    CarsAndBidsScraper,
    ClassicDotComScraper,
    CraigslistScraper,
    PCarMarketScraper,
    BoxsterForumScraper,
    RennlistScraper,
    Planet9Scraper,
]


@dataclass
class HuntStats:
    fetched: int = 0
    new: int = 0
    rejected: int = 0
    notion_pages: int = 0
    notifications: int = 0
    errors: int = 0


def setup_logging() -> None:
    level = os.environ.get("BOXSTER_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )


def run(
    db: Database,
    notion: NotionSink,
    notifier: Notifier,
    scrapers: list[BaseScraper],
    dry_run_scrapers: bool = False,
) -> HuntStats:
    stats = HuntStats()
    all_listings: list[Listing] = []

    for scraper in scrapers:
        if dry_run_scrapers:
            log.info("[dry-run] skipping live fetch for %s", scraper.source)
            continue
        try:
            fetched = scraper.fetch_listings()
            log.info("%s: fetched %d listings", scraper.source, len(fetched))
            stats.fetched += len(fetched)
            all_listings.extend(fetched)
        except Exception:
            log.exception("scraper %s failed", scraper.source)
            stats.errors += 1

    new_listings = db.filter_new(all_listings)
    stats.new = len(new_listings)
    log.info("Dedup: %d new of %d total", stats.new, stats.fetched)

    for listing in new_listings:
        score_listing(listing)
        if listing.tier == "REJECTED":
            stats.rejected += 1
            db.record(listing)
            continue
        if listing.tier == "🥉 MARGINAL":
            db.record(listing)
            continue

        page_id = notion.create_listing_page(listing)
        stats.notion_pages += 1
        results = notifier.dispatch(listing)
        if any(results.values()):
            stats.notifications += 1
        db.record(listing, notion_page_id=page_id)

    log.info(
        "Hunt complete: fetched=%d new=%d rejected=%d notion=%d notify=%d errors=%d",
        stats.fetched,
        stats.new,
        stats.rejected,
        stats.notion_pages,
        stats.notifications,
        stats.errors,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boxster-hunt")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip live HTTP from scrapers; only exercise the rest of the pipeline.",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    setup_logging()

    db_path = os.environ.get("BOXSTER_DB_PATH", "boxster.db")
    db = Database(db_path)
    notion = NotionSink()
    notifier = Notifier()
    scrapers = [cls() for cls in ALL_SCRAPERS]

    stats = run(db, notion, notifier, scrapers, dry_run_scrapers=args.dry_run)
    return 0 if stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
