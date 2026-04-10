"""Base scraper class. Handles HTTP session, UA rotation, and rate limiting."""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime

import requests

from boxster_hunter.models import Listing

USER_AGENTS = [
    # A small pool of recent desktop UAs. Real Boxster hunters use real browsers.
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/124.0",
]

DEFAULT_TIMEOUT = 15
DEFAULT_MIN_INTERVAL = 1.0  # seconds between requests per source


class BaseScraper(ABC):
    """All scrapers inherit from this. Subclasses implement fetch_listings()."""

    source: str = "unknown"

    def __init__(
        self,
        session: requests.Session | None = None,
        min_interval: float = DEFAULT_MIN_INTERVAL,
    ):
        self.session = session or requests.Session()
        self.min_interval = min_interval
        self._last_request_at: float = 0.0
        self.log = logging.getLogger(f"boxster.{self.source}")

    def _rotate_ua(self) -> str:
        return random.choice(USER_AGENTS)

    def http_get(self, url: str, **kwargs) -> requests.Response:
        """GET with rate limiting + UA rotation."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("User-Agent", self._rotate_ua())
        headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        resp = self.session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs)
        self._last_request_at = time.monotonic()
        return resp

    @abstractmethod
    def fetch_listings(self) -> list[Listing]:
        """Return a list of Listings from this source. Network calls allowed."""

    @abstractmethod
    def parse(self, payload: str | bytes) -> list[Listing]:
        """Parse a raw payload (HTML/JSON/RSS body) into Listings.

        Kept separate from ``fetch_listings`` so we can unit-test parsing
        against committed fixtures with no network access.
        """

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)
