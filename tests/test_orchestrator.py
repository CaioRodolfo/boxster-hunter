"""End-to-end orchestrator test using fake scrapers and dry-run sinks.

This is the integration test from the spec: scored listing → Notion payload
shape, dedup on second run produces zero new listings.
"""

import json
from pathlib import Path

from boxster_hunter.db import Database
from boxster_hunter.main import run
from boxster_hunter.notifier import Notifier
from boxster_hunter.notion_sink import NotionSink
from boxster_hunter.scrapers.base import BaseScraper
from boxster_hunter.scrapers.carsandbids import CarsAndBidsScraper

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCarsAndBids(BaseScraper):
    """Fake scraper that returns the committed Cars & Bids fixture, no HTTP."""

    source = "carsandbids"

    def fetch_listings(self):
        payload = (FIXTURES / "carsandbids" / "search.json").read_text()
        return CarsAndBidsScraper().parse(payload)

    def parse(self, payload):
        return CarsAndBidsScraper().parse(payload)


def test_orchestrator_end_to_end_dedup(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)

    db = Database(tmp_path / "hunt.db")
    notion = NotionSink()  # dry-run
    notifier = Notifier()  # dry-run
    scraper = FakeCarsAndBids()

    # First run: 3 listings, 1 GOLD + 1 STRONG + 1 REJECTED Tiptronic
    stats1 = run(db, notion, notifier, [scraper])
    assert stats1.fetched == 3
    assert stats1.new == 3
    assert stats1.rejected == 1
    assert stats1.notion_pages == 2  # GOLD + STRONG (REJECTED skipped)
    assert stats1.notifications == 2  # both notify (GOLD + STRONG)
    assert stats1.errors == 0

    # Second run: same listings, dedup should reject all
    stats2 = run(db, notion, notifier, [scraper])
    assert stats2.fetched == 3
    assert stats2.new == 0
    assert stats2.notion_pages == 0
    assert stats2.notifications == 0


def test_orchestrator_handles_scraper_failure(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)

    class BrokenScraper(BaseScraper):
        source = "broken"

        def fetch_listings(self):
            raise RuntimeError("nope")

        def parse(self, payload):
            return []

    db = Database(tmp_path / "hunt.db")
    notion = NotionSink()
    notifier = Notifier()
    stats = run(db, notion, notifier, [BrokenScraper(), FakeCarsAndBids()])
    # One scraper crashed but the other still produced results
    assert stats.errors == 1
    assert stats.fetched == 3


def test_dry_run_skips_fetching(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)

    class TripWire(BaseScraper):
        source = "tripwire"

        def fetch_listings(self):
            raise AssertionError("fetch_listings should not be called in dry-run")

        def parse(self, payload):
            return []

    db = Database(tmp_path / "hunt.db")
    notion = NotionSink()
    notifier = Notifier()
    stats = run(db, notion, notifier, [TripWire()], dry_run_scrapers=True)
    assert stats.fetched == 0


def test_fixtures_are_valid_json():
    # Sanity check on the JSON fixture so a typo gets caught early.
    data = json.loads((FIXTURES / "carsandbids" / "search.json").read_text())
    assert "auctions" in data
    assert len(data["auctions"]) == 3
