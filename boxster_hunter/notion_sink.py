"""Notion API client. Generic, target-aware.

A single ``NotionSink`` instance is bound to one ``TargetConfig``. The target
provides:

  * ``notion_database_id_env`` — the env var name that holds the destination
    database id at runtime
  * ``build_notion_properties(listing)`` — a function that converts a scored
    listing into the JSON ``properties`` dict for a Notion ``create_page`` call

When ``NOTION_API_KEY`` or the target's database id env var is unset, the
sink runs in dry-run mode: every call logs what would have been sent and
returns a synthetic page id.
"""

from __future__ import annotations

import logging
import os

import requests

from boxster_hunter.models import Listing
from boxster_hunter.targets.base import TargetConfig

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

log = logging.getLogger("boxster.notion")


class NotionSink:
    def __init__(
        self,
        target: TargetConfig,
        api_key: str | None = None,
        database_id: str | None = None,
        session: requests.Session | None = None,
    ):
        self.target = target
        self.api_key = api_key or os.environ.get("NOTION_API_KEY")
        self.database_id = database_id or os.environ.get(target.notion_database_id_env)
        self.session = session or requests.Session()
        self.dry_run = not (self.api_key and self.database_id)
        if self.dry_run:
            log.info(
                "Notion sink for %s in dry-run mode (NOTION_API_KEY or %s unset)",
                target.target_id,
                target.notion_database_id_env,
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def create_listing_page(self, listing: Listing) -> str:
        if self.target.build_notion_properties is None:
            raise RuntimeError(
                f"target {self.target.target_id} has no build_notion_properties"
            )
        properties = self.target.build_notion_properties(listing)
        body = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        }

        if self.dry_run:
            title_fn = self.target.notion_page_title
            page_title = title_fn(listing) if title_fn else listing.title
            log.info(
                "[dry-run] %s would create Notion page: tier=%s score=%d title=%r",
                self.target.target_id,
                listing.tier,
                listing.score,
                page_title,
            )
            return f"dry-run-{self.target.target_id}-{listing.source}-{listing.source_id}"

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
