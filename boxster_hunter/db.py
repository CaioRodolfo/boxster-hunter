"""SQLite deduplication layer.

Tracks every listing URL we've seen and the score we last assigned it. Before
processing a fresh scrape, we check if the URL is already in the table; if so,
we skip it (and optionally update the last_score if the listing has changed).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from boxster_hunter.models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_score INTEGER,
    last_tier TEXT,
    notion_page_id TEXT,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_seen_url ON seen_listings(url);
CREATE INDEX IF NOT EXISTS idx_seen_first_seen ON seen_listings(first_seen);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def has_seen(self, url: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_listings WHERE url = ?", (url,)
            ).fetchone()
            return row is not None

    def record(self, listing: Listing, notion_page_id: str | None = None) -> None:
        """Insert or update a listing in the dedup table.

        Dedups by ``(source, source_id)`` — the stable identifier. Scrapers
        sometimes emit the same thread with slightly different URLs (sticky
        threads rendered in multiple sections, trailing slashes, session
        params), so the URL is not reliable as a primary key. On conflict we
        refresh the URL/score/tier and preserve the existing notion_page_id
        unless a new one is supplied.
        """
        with self._conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO seen_listings (source, source_id, url, last_score, last_tier, notion_page_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, source_id) DO UPDATE SET
                        url = excluded.url,
                        last_score = excluded.last_score,
                        last_tier = excluded.last_tier,
                        notion_page_id = COALESCE(excluded.notion_page_id, seen_listings.notion_page_id)
                    """,
                    (
                        listing.source,
                        listing.source_id,
                        listing.url_str,
                        listing.score,
                        listing.tier,
                        notion_page_id,
                    ),
                )
            except sqlite3.IntegrityError:
                # Legacy cached DBs still carry ``UNIQUE`` on ``url``. If the
                # upsert hits that constraint (a different source_id now uses
                # an already-seen URL), fall back to updating the existing
                # row by URL so one bad listing doesn't kill the whole run.
                conn.execute(
                    """
                    UPDATE seen_listings
                    SET last_score = ?,
                        last_tier = ?,
                        notion_page_id = COALESCE(?, notion_page_id)
                    WHERE url = ?
                    """,
                    (listing.score, listing.tier, notion_page_id, listing.url_str),
                )

    def filter_new(self, listings: list[Listing]) -> list[Listing]:
        """Return only listings whose URL we have not seen yet."""
        if not listings:
            return []
        urls = [item.url_str for item in listings]
        placeholders = ",".join("?" * len(urls))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT url FROM seen_listings WHERE url IN ({placeholders})", urls
            ).fetchall()
            seen = {row["url"] for row in rows}
        return [item for item in listings if item.url_str not in seen]

    def cleanup_older_than(self, days: int = 90) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM seen_listings WHERE first_seen < ?", (cutoff.isoformat(),)
            )
            return cur.rowcount

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM seen_listings").fetchone()[0]
