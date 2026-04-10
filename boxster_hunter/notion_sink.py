"""Notion API client for the 986 Hunt database.

Talks directly to the Notion REST API (no SDK dependency). When
``NOTION_API_KEY`` or ``NOTION_DATABASE_ID`` is unset, the sink runs in
dry-run mode: every call logs what *would* have been sent and returns a
synthetic page id. This keeps the orchestrator simple — there's no
"if notion enabled" branching upstream.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from boxster_hunter.models import Listing

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

SOURCE_DISPLAY = {
    "carsandbids": "Cars & Bids",
    "classic.com": "Classic.com",
    "craigslist": "Craigslist",
    "pcarmarket": "PCARMARKET",
    "986forum": "986forum",
    "rennlist": "Rennlist",
    "planet9": "Planet-9",
}

log = logging.getLogger("boxster.notion")


class NotionSink:
    def __init__(
        self,
        api_key: str | None = None,
        database_id: str | None = None,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key or os.environ.get("NOTION_API_KEY")
        self.database_id = database_id or os.environ.get("NOTION_DATABASE_ID")
        self.session = session or requests.Session()
        self.dry_run = not (self.api_key and self.database_id)
        if self.dry_run:
            log.info("Notion sink in dry-run mode (no API key or database id)")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def create_listing_page(self, listing: Listing) -> str:
        """Create a page in the 986 Hunt database for the given listing.

        Returns the new page id (or a synthetic ``"dry-run-..."`` id when the
        sink has no credentials).
        """
        properties = build_properties(listing)
        body = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        if self.dry_run:
            log.info(
                "[dry-run] would create Notion page: tier=%s score=%d title=%r",
                listing.tier,
                listing.score,
                _title_for(listing),
            )
            return f"dry-run-{listing.source}-{listing.source_id}"

        resp = self.session.post(
            f"{NOTION_API}/pages",
            headers=self._headers(),
            json=body,
            timeout=20,
        )
        if not resp.ok:
            log.error("Notion API error %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()["id"]


def build_properties(listing: Listing) -> dict[str, Any]:
    """Convert a scored Listing into the Notion properties JSON payload."""
    title = _title_for(listing)
    color_category = _color_category(listing)
    ims_status = _ims_status(listing)
    source_display = SOURCE_DISPLAY.get(listing.source, listing.source)
    transmission = listing.transmission or "Unknown"
    flags = _normalize_flags(listing.flags)

    props: dict[str, Any] = {
        "Title": {"title": [{"text": {"content": title}}]},
        "Tier": {"select": {"name": listing.tier}},
        "Score": {"number": listing.score},
        "Source": {"select": {"name": source_display}},
        "Transmission": {"select": {"name": transmission}},
        "IMS Status": {"select": {"name": ims_status}},
        "URL": {"url": listing.url_str},
        "First Seen": {"date": {"start": listing.first_seen.isoformat()}},
    }

    if color_category:
        props["Color"] = {"select": {"name": color_category}}
    if listing.year is not None:
        props["Year"] = {"number": listing.year}
    if listing.mileage is not None:
        props["Mileage"] = {"number": listing.mileage}
    if listing.price is not None:
        props["Price"] = {"number": listing.price}
    if listing.location:
        props["Location"] = {"rich_text": [{"text": {"content": listing.location}}]}
    if listing.auction_end:
        props["Auction End"] = {"date": {"start": listing.auction_end.isoformat()}}
    if flags:
        props["Flags"] = {"multi_select": [{"name": f} for f in flags]}

    return props


def _title_for(listing: Listing) -> str:
    year = listing.year or "????"
    color = (listing.color_match or {}).get("display") or listing.color_exterior or "Unknown"
    src = SOURCE_DISPLAY.get(listing.source, listing.source)
    return f"{year} {color} Boxster S — {src}"


def _color_category(listing: Listing) -> str | None:
    if not listing.color_match:
        return None
    return listing.color_match.get("display")


def _ims_status(listing: Listing) -> str:
    if listing.has_ims_solution:
        return "Solution"
    if listing.has_ims_retrofit:
        return "Retrofit"
    if listing.has_ims_replaced:
        return "Replaced (generic)"
    return "Unknown"


# Canonical multi_select options created when the database was set up.
_CANONICAL_FLAGS = {
    "🏆 IMS Solution (permanent fix)",
    "✅ IMS Retrofit",
    "✅ IMS replaced (verify type)",
    "⚠️ IMS status unknown",
    "✅ 6-speed manual",
    "⚠️ Transmission unclear — verify",
    "📋 Service records mentioned",
    "📉 Low miles",
    "✨ RARE",
}


def _normalize_flags(flags: list[str]) -> list[str]:
    """Map dynamic flag strings (e.g. "📉 Low miles (47,500)") to canonical option names.

    Notion multi_select options must match an existing or new option name. To
    avoid creating one option per mileage value, we collapse anything that
    starts with a known prefix to its canonical form.
    """
    out: list[str] = []
    for flag in flags:
        # Skip rejection flags — they don't go in the multi-select.
        if flag.startswith("❌"):
            continue
        if flag in _CANONICAL_FLAGS:
            out.append(flag)
            continue
        if flag.startswith("📉 Low miles"):
            out.append("📉 Low miles")
        elif flag.startswith("✨ RARE"):
            out.append("✨ RARE")
        else:
            # Brand-new flag — let Notion auto-create the option.
            out.append(flag)
    return out
