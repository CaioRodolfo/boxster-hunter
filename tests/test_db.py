"""SQLite dedup tests."""

from boxster_hunter.db import Database
from tests.conftest import make_listing


def test_record_and_has_seen(tmp_path):
    db = Database(tmp_path / "test.db")
    listing = make_listing(url="https://example.com/a")
    assert db.has_seen("https://example.com/a") is False
    db.record(listing)
    assert db.has_seen("https://example.com/a") is True
    assert db.count() == 1


def test_filter_new_returns_only_unseen(tmp_path):
    db = Database(tmp_path / "test.db")
    a = make_listing(source_id="a", url="https://example.com/a")
    b = make_listing(source_id="b", url="https://example.com/b")
    db.record(a)
    new = db.filter_new([a, b])
    assert len(new) == 1
    assert new[0].url_str == "https://example.com/b"


def test_record_is_idempotent_on_url(tmp_path):
    db = Database(tmp_path / "test.db")
    listing = make_listing(url="https://example.com/a", score=55)
    db.record(listing)
    listing.score = 88
    listing.tier = "🥇 STRONG"
    db.record(listing)
    assert db.count() == 1


def test_record_upserts_when_source_id_matches_but_url_changes(tmp_path):
    # Regression: vBulletin sticky threads appear twice with slightly
    # different hrefs but the same source_id. Before the fix, the second
    # record() raised sqlite3.IntegrityError on the composite UNIQUE.
    db = Database(tmp_path / "test.db")
    first = make_listing(source="yotatech", source_id="t123", url="https://example.com/t/123")
    second = make_listing(source="yotatech", source_id="t123", url="https://example.com/t/123/")
    db.record(first)
    db.record(second)  # must not raise
    assert db.count() == 1


def test_filter_new_handles_empty(tmp_path):
    db = Database(tmp_path / "test.db")
    assert db.filter_new([]) == []
