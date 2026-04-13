"""Orchestrator. Wires scrapers → dedup → enrichment → per-target scoring → sinks.

Multi-target architecture:

  1. Each scraper runs *once* per cron, regardless of how many targets it serves.
  2. Listings are deduped against a single SQLite table — the URL is the key.
  3. Shallow listings are enriched (detail-fetched) *once* before any scoring.
  4. Each new listing is then scored against *every* registered target. Targets
     reject listings whose title doesn't match their keyword, so most listings
     only get meaningfully scored by one target.
  5. Each target writes successful matches to its own Notion DB and Slack channel.

Run modes:

  python -m boxster_hunter.main             # live run (uses env vars)
  python -m boxster_hunter.main --dry-run   # skip live HTTP from scrapers
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from copy import deepcopy
from dataclasses import dataclass, field

from dotenv import load_dotenv

from boxster_hunter.db import Database
from boxster_hunter.models import Listing
from boxster_hunter.notifier import Notifier
from boxster_hunter.notion_sink import NotionSink
from boxster_hunter.scoring import score_listing
from boxster_hunter.scrapers.audiworld import AudiWorldScraper
from boxster_hunter.scrapers.base import BaseScraper
from boxster_hunter.scrapers.boxster_forum import BoxsterForumScraper
from boxster_hunter.scrapers.bringatrailer import BringATrailerScraper
from boxster_hunter.scrapers.carsandbids import CarsAndBidsScraper
from boxster_hunter.scrapers.classic_dot_com import ClassicDotComScraper
from boxster_hunter.scrapers.pcarmarket import PCarMarketScraper
from boxster_hunter.scrapers.planet9 import Planet9Scraper
from boxster_hunter.scrapers.rennlist import RennlistScraper
from boxster_hunter.targets import ALL_TARGETS
from boxster_hunter.targets.base import TargetConfig

log = logging.getLogger("boxster.main")

# Craigslist + AudiZine are intentionally absent — see their scraper modules
# for context (both are Cloudflare-gated and require a residential proxy).
ALL_SCRAPERS: list[type[BaseScraper]] = [
    CarsAndBidsScraper,
    BringATrailerScraper,
    ClassicDotComScraper,
    PCarMarketScraper,
    BoxsterForumScraper,
    RennlistScraper,
    Planet9Scraper,
    AudiWorldScraper,
]


@dataclass
class TargetStats:
    notion_pages: int = 0
    notifications: int = 0
    rejected: int = 0


@dataclass
class HuntStats:
    fetched: int = 0
    new: int = 0
    enriched: int = 0
    errors: int = 0
    per_target: dict[str, TargetStats] = field(default_factory=dict)


def setup_logging() -> None:
    level = os.environ.get("BOXSTER_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )


# Listings whose description is shorter than this are considered "shallow"
# (just the title, no body). The orchestrator fetches the detail page and
# replaces the description before scoring. RSS-sourced listings (Cars & Bids,
# BaT) already exceed this threshold and skip enrichment automatically.
SHALLOW_DESCRIPTION_THRESHOLD = 200


def _listing_is_for_target(listing: Listing, target: TargetConfig) -> bool:
    """Cheap pre-check: does the listing's title mention this target at all?

    Used to decide which targets get the detail-fetch enrichment HTTP cost.
    The full filter logic lives in the scoring engine; this is just a hint.
    """
    text = f"{listing.title} {listing.description}".lower()
    return target.title_keyword in text


def run(
    db: Database,
    targets: list[TargetConfig],
    sinks_by_target: dict[str, NotionSink],
    notifiers_by_target: dict[str, Notifier],
    scrapers: list[BaseScraper],
    dry_run_scrapers: bool = False,
) -> HuntStats:
    stats = HuntStats(per_target={t.target_id: TargetStats() for t in targets})
    all_listings: list[Listing] = []
    scraper_by_source = {s.source: s for s in scrapers}

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
        # Decide whether to enrich BEFORE per-target scoring. Enrichment is
        # worth the HTTP cost only if (a) the listing is shallow and (b) at
        # least one target's title keyword shows up in the title. This keeps
        # us from re-fetching every Ford F-250 on Cars & Bids RSS.
        is_shallow = len(listing.description) < SHALLOW_DESCRIPTION_THRESHOLD
        any_target_interested = any(_listing_is_for_target(listing, t) for t in targets)
        if is_shallow and any_target_interested:
            scraper = scraper_by_source.get(listing.source)
            if scraper is not None and scraper.enrich_description(listing):
                stats.enriched += 1

        # Score against every target. Each target rejects listings whose
        # title keyword doesn't match, so most listings only score
        # meaningfully against one target. We keep separate scored copies so
        # one target's side effects don't contaminate another target.
        any_match = False
        for target in targets:
            scored = score_listing(deepcopy(listing), target)
            target_stats = stats.per_target[target.target_id]

            if scored.tier == "REJECTED":
                target_stats.rejected += 1
                continue
            if scored.tier == "🥉 MARGINAL":
                continue

            sink = sinks_by_target[target.target_id]
            notifier = notifiers_by_target[target.target_id]
            page_id = sink.create_listing_page(scored)
            target_stats.notion_pages += 1
            results = notifier.dispatch(scored)
            if any(results.values()):
                target_stats.notifications += 1
            any_match = True
            # Only record the *first* matching target's notion page id on the
            # dedup row; we just need to remember we've seen the URL.
            if any_match:
                db.record(scored, notion_page_id=page_id)

        if not any_match:
            db.record(listing)

    if stats.enriched:
        log.info("Enriched %d shallow listings via detail fetch", stats.enriched)

    log.info(
        "Hunt complete: fetched=%d new=%d enriched=%d errors=%d",
        stats.fetched,
        stats.new,
        stats.enriched,
        stats.errors,
    )
    for tid, ts in stats.per_target.items():
        log.info(
            "  %s: notion=%d notify=%d rejected=%d",
            tid,
            ts.notion_pages,
            ts.notifications,
            ts.rejected,
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
    targets = ALL_TARGETS
    sinks_by_target = {t.target_id: NotionSink(target=t) for t in targets}
    notifiers_by_target = {t.target_id: Notifier(target=t) for t in targets}
    scrapers = [cls() for cls in ALL_SCRAPERS]

    stats = run(
        db,
        targets,
        sinks_by_target,
        notifiers_by_target,
        scrapers,
        dry_run_scrapers=args.dry_run,
    )
    # Exit non-zero only if *every* source failed.
    all_sources_failed = stats.errors > 0 and stats.fetched == 0
    return 1 if all_sources_failed else 0


if __name__ == "__main__":
    sys.exit(main())
