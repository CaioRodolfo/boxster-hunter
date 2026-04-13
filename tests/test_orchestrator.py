"""End-to-end orchestrator test using fake scrapers and dry-run sinks.

This is the integration test from the spec: scored listings flow through dedup
and a second run should produce zero new listings.
"""

import json
from pathlib import Path

from boxster_hunter.db import Database
from boxster_hunter.main import run
from boxster_hunter.notifier import Notifier
from boxster_hunter.notion_sink import NotionSink
from boxster_hunter.scrapers.base import BaseScraper
from boxster_hunter.scrapers.classic_dot_com import ClassicDotComScraper

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClassic(BaseScraper):
    """Fake scraper that returns the committed Classic.com fixture, no HTTP.

    Classic.com is the most listing-rich fixture in the suite (~20 cards),
    which makes it the best one for exercising the orchestrator's batching,
    dedup, and tier-routing logic without flakiness. Enrichment is stubbed so
    the test never makes a network call.
    """

    source = "classic.com"

    def fetch_listings(self):
        return ClassicDotComScraper().parse((FIXTURES / "classic_dot_com" / "search.html").read_bytes())

    def parse(self, payload):
        return ClassicDotComScraper().parse(payload)

    def enrich_description(self, listing):
        # No-op: tests must never hit the network.
        return False


def test_orchestrator_end_to_end_dedup(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)

    db = Database(tmp_path / "hunt.db")
    notion = NotionSink()  # dry-run
    notifier = Notifier()  # dry-run
    scraper = FakeClassic()

    # First run: process every listing in the fixture
    stats1 = run(db, notion, notifier, [scraper])
    assert stats1.fetched > 0
    assert stats1.new == stats1.fetched
    assert stats1.errors == 0
    # Notion pages = anything not REJECTED and not MARGINAL
    assert stats1.notion_pages >= 0
    assert stats1.notion_pages + stats1.rejected <= stats1.fetched

    # Second run: same listings, dedup should report zero new
    stats2 = run(db, notion, notifier, [scraper])
    assert stats2.fetched == stats1.fetched
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
    healthy = FakeClassic()
    stats = run(db, notion, notifier, [BrokenScraper(), healthy])
    # One scraper crashed but the other still produced results
    assert stats.errors == 1
    assert stats.fetched > 0


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


def test_pcarmarket_fixture_is_valid_json():
    # Sanity check that the PCARMARKET API fixture parses cleanly.
    data = json.loads((FIXTURES / "pcarmarket" / "api.json").read_text())
    assert "results" in data


def test_enrichment_promotes_shallow_listing(tmp_path, monkeypatch):
    """A title-only listing should be re-fetched, re-scored, and promoted."""
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)

    from datetime import UTC, datetime

    from boxster_hunter.models import Listing
    from boxster_hunter.scrapers.base import BaseScraper

    class StubScraper(BaseScraper):
        source = "stub"

        def fetch_listings(self):
            # One shallow listing: title only, looks like 30 points (year ok,
            # 6-speed in title, no IMS) — should land MARGINAL pre-enrichment.
            return [
                Listing(
                    source=self.source,
                    source_id="abc",
                    url="https://example.com/abc",
                    first_seen=datetime.now(UTC),
                    last_updated=datetime.now(UTC),
                    title="2004 Porsche Boxster S 3.2L 6-speed",
                    description="2004 Porsche Boxster S 3.2L 6-speed",
                )
            ]

        def parse(self, payload):
            return []

        def enrich_description(self, listing):
            # Simulate a detail fetch that uncovers IMS Solution + color.
            listing.description = (
                "Long-form body: this 2004 Boxster S has had the LN Engineering "
                "IMS Solution installed by a Porsche specialist. 6-speed manual. "
                "Lagoon Green Metallic over black. Comprehensive service records."
            )
            return True

    db = Database(tmp_path / "hunt.db")
    notion = NotionSink()
    notifier = Notifier()
    stats = run(db, notion, notifier, [StubScraper()])

    assert stats.fetched == 1
    assert stats.notion_pages == 1
    assert stats.notifications == 1


def test_enrichment_skipped_for_already_rich_listings(tmp_path, monkeypatch):
    """If a listing arrives with a long description, enrich_description is not called."""
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)

    from datetime import UTC, datetime

    from boxster_hunter.models import Listing
    from boxster_hunter.scrapers.base import BaseScraper

    enrich_calls = {"count": 0}

    class RichScraper(BaseScraper):
        source = "rich"

        def fetch_listings(self):
            return [
                Listing(
                    source=self.source,
                    source_id="rich-1",
                    url="https://example.com/rich-1",
                    first_seen=datetime.now(UTC),
                    last_updated=datetime.now(UTC),
                    title="2004 Porsche Boxster S",
                    description="x" * 500,  # already rich
                )
            ]

        def parse(self, payload):
            return []

        def enrich_description(self, listing):
            enrich_calls["count"] += 1
            return True

    db = Database(tmp_path / "hunt.db")
    run(db, NotionSink(), Notifier(), [RichScraper()])
    assert enrich_calls["count"] == 0
