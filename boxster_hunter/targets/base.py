"""Per-target hunting configuration.

Each ``TargetConfig`` instance fully describes one car-shaped thing the system
hunts for: which scrapers it consumes, which year range counts, which patterns
disqualify a listing, which patterns add positive score, the color map, the
Notion database to write into, and the Slack webhook to ping.

The scoring engine in ``boxster_hunter.scoring`` is *generic* — it takes a
``TargetConfig`` and applies its rules. There is no car-specific code in the
engine. To add a new car, write a new ``TargetConfig`` and register it in
``boxster_hunter.targets.__init__``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from boxster_hunter.models import Listing


@dataclass
class Disqualifier:
    """A pattern set that immediately rejects a listing.

    The disqualifier fires when *any* pattern in ``patterns`` matches the
    full lowercased text of the listing AND, optionally, *none* of the
    patterns in ``require_absence`` match. The ``require_absence`` knob is
    what lets us encode rules like "reject 5-speed UNLESS the listing also
    mentions 6-speed somewhere" — the original Boxster spec used this to
    distinguish base 5MTs from S models with a 6MT.
    """

    reason: str
    patterns: list[str]
    require_absence: list[str] = field(default_factory=list)


@dataclass
class ScoringRule:
    """A single positive-signal scoring rule. All matches are additive.

    If the rule does not match, ``fallback_flag`` (when set) is appended to
    the listing's flag list with no score change. This is how we represent
    "I expected to see a 6-speed mention here; I didn't, so flag it for
    manual verification" without rejecting the listing outright.
    """

    points: int
    flag: str
    patterns: list[str]
    side_effect: Callable[[Listing], None] | None = None
    fallback_flag: str | None = None


@dataclass
class TieredRule:
    """A scoring rule with multiple tiers — the *first* matching tier wins.

    Tiers are evaluated top-to-bottom, so list them best-to-worst (e.g. for
    IMS work, ``IMS Solution`` comes before ``IMS Retrofit`` comes before
    a generic ``IMS replaced`` mention). If no tier matches and
    ``fallback_flag`` is set, that flag is appended to the listing instead
    of any score.
    """

    tiers: list[ScoringRule]
    fallback_flag: str | None = None


@dataclass
class TargetConfig:
    """Everything the orchestrator + scoring engine need to hunt for one car."""

    # Identity
    target_id: str
    display_name: str
    emoji: str

    # Routing — which listings count for this target
    title_keyword: str  # required substring (lowercased) in the listing text
    year_range: tuple[int, int]  # inclusive on both ends

    # Scoring
    disqualifiers: list[Disqualifier]
    positive_rules: list[ScoringRule]
    tiered_rules: list[TieredRule]
    colors: dict[str, dict[str, Any]]  # passed to match_color()
    color_base_points: int = 20
    color_rarity_bonus: int = 10
    color_rarity_set: tuple[str, ...] = ("rare", "very rare", "unicorn")

    # Optional bonuses
    low_mileage_threshold: int | None = None
    low_mileage_points: int = 5
    service_records_keywords: tuple[str, ...] = ()
    service_records_points: int = 5

    # Per-target tier thresholds — (gold, strong, review). Defaults match the
    # original spec: 90/70/50. Lower a target's review threshold to widen its
    # notification net; useful for hunts where the spec is hard to satisfy
    # automatically and the user would rather review more candidates.
    tier_thresholds: tuple[int, int, int] = (90, 70, 50)

    # Output destinations — env var *names*, not the secrets themselves.
    # The orchestrator looks them up at runtime so we don't have to bake
    # secrets into Python code.
    notion_database_id_env: str = "NOTION_DATABASE_ID"
    slack_webhook_env: str = "SLACK_WEBHOOK_URL"

    # Notion property builder — takes a scored Listing and returns the JSON
    # ``properties`` dict for a Notion API create-page call. Each target owns
    # its schema (S3 has B&O / Trim / Haldex columns Boxsters don't have).
    # Default is a no-op so the dataclass can be constructed without it; real
    # targets must override.
    build_notion_properties: Callable[[Listing], dict[str, Any]] | None = None

    # Notion page title builder — generates the human-readable title shown at
    # the top of each Notion page. Default falls back to "{year} {model} from
    # {source}" using the listing's bare fields.
    notion_page_title: Callable[[Listing], str] | None = None


# ---------------------------------------------------------------------------
# Generic helpers used by every target's scoring config
# ---------------------------------------------------------------------------


def any_match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def match_color(text: str, color_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first matching target color for a listing, or None.

    Aliases match case-insensitively against ``text``. Paint codes match
    exact-case against the original-case ``text`` so we don't grab a stray
    ``"12H"`` out of an unrelated phrase. The matcher is generic: each
    ``TargetConfig`` provides its own ``colors`` map.
    """
    text_lower = text.lower()
    for category, data in color_map.items():
        for variant in data["variants"]:
            for alias in variant["aliases"]:
                if alias in text_lower:
                    return _match_dict(category, data, variant, "alias")
            for code in variant["codes"]:
                if code in text:
                    return _match_dict(category, data, variant, "code")
    return None


def _match_dict(
    category: str,
    data: dict[str, Any],
    variant: dict[str, Any],
    match_type: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "display": data["display"],
        "emoji": data["emoji"],
        "name": variant["name"],
        "rarity": variant["rarity"],
        "match_type": match_type,
    }
