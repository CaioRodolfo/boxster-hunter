"""Shared helpers for RSS-based scrapers.

Both Cars & Bids and Bring a Trailer publish WordPress-style RSS feeds with
rich HTML descriptions. The three helpers below are identical between them —
extracted here so a fix to one gets applied to both.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def strip_html(s: str) -> str:
    """RSS <description> bodies are HTML; extract plain text for scoring."""
    if not s:
        return ""
    return BeautifulSoup(s, "lxml").get_text(" ", strip=True)


def first_year(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def source_id_from_url(url: str) -> str:
    """Return the last meaningful segment of a listing URL.

    Cars & Bids URLs look like ``/auctions/{shortid}/{slug}`` — the short id
    is penultimate. BaT URLs look like ``/listing/{slug}/`` — the slug is
    last. This helper handles both.
    """
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] not in ("auctions", "listing"):
        return parts[-2]
    return parts[-1]
