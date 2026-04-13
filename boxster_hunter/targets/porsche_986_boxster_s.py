"""986 Boxster S target — 2003-2004 Porsche Boxster S, 6-speed, IMS-addressed.

This file is the single source of truth for every car-specific decision the
hunter makes about Boxsters. All the patterns, color codes, weights, and
disqualifiers live here. The scoring engine knows nothing about Porsches.

To tune the hunt: edit this file. Add a pattern, change a weight, add a color
variant. The engine picks it up on the next run.
"""

from __future__ import annotations

from typing import Any

from boxster_hunter.models import Listing
from boxster_hunter.sources import display_name
from boxster_hunter.targets.base import (
    Disqualifier,
    ScoringRule,
    TargetConfig,
    TieredRule,
)

# ---------------------------------------------------------------------------
# Colors — paint codes sourced from RennTech.org, only colors offered on 2003-2004
# ---------------------------------------------------------------------------

COLORS: dict[str, dict[str, Any]] = {
    "green": {
        "display": "Green",
        "emoji": "🟢",
        "variants": [
            {
                "name": "Lagoon Green Metallic",
                "aliases": ["lagoon green", "dark teal", "green lagoon", "lagogrün"],
                "codes": ["M6W"],
                "years": [2004],
                "rarity": "very rare",
            },
            {
                "name": "Pine Green Metallic",
                "aliases": ["pine green"],
                "codes": ["2B4", "22E"],
                "years": [2003, 2004],
                "rarity": "uncommon",
            },
        ],
    },
    "yellow": {
        "display": "Yellow",
        "emoji": "💛",
        "variants": [
            {
                "name": "Speed Yellow",
                "aliases": ["speed yellow", "speedgelb"],
                "codes": ["12H", "12G"],
                "years": [2003, 2004],
                "rarity": "uncommon",
            },
            {
                "name": "Fayence Yellow",
                "aliases": ["fayence yellow", "fayencegelb"],
                "codes": [],
                "years": [2004],
                "rarity": "unicorn",
            },
        ],
    },
    "navy_blue": {
        "display": "Navy Blue",
        "emoji": "🔵",
        "variants": [
            {
                "name": "Lapis Blue Metallic",
                "aliases": ["lapis blue", "lapisblau"],
                "codes": ["3A8", "3A9"],
                "years": [2003],
                "rarity": "uncommon",
            },
            {
                "name": "Cobalt Blue Metallic",
                "aliases": ["cobalt blue", "cobaltblau"],
                "codes": ["3C8", "37U"],
                "years": [2003, 2004],
                "rarity": "uncommon",
            },
            {
                "name": "Midnight Blue Metallic",
                "aliases": ["midnight blue", "dark blue pearl", "nachtblau"],
                "codes": ["39C", "37W"],
                "years": [2003],
                "rarity": "uncommon",
            },
        ],
    },
    "red": {
        "display": "Red",
        "emoji": "❤️",
        "variants": [
            {
                "name": "Guards Red",
                "aliases": ["guards red", "indian red", "indischrot"],
                "codes": ["84A", "80K"],
                "years": [2003, 2004],
                "rarity": "common",
            },
            {
                "name": "Orient Red Metallic",
                "aliases": ["orient red", "orientrot"],
                "codes": ["843", "8A4"],
                "years": [2003],
                "rarity": "uncommon",
            },
            {
                "name": "Carmona Red Metallic",
                "aliases": ["carmona red", "carmonarot"],
                "codes": [],
                "years": [2004],
                "rarity": "rare",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

IMS_SOLUTION_PATTERNS = [
    r"ims\s+solution",
    r"ln\s+engineering\s+solution",
    r"ims[-\s]solution",
]

IMS_RETROFIT_PATTERNS = [
    r"ims\s+retrofit",
    r"ln\s+engineering\s+retrofit",
    r"ln\s+retrofit",
    r"ims[-\s]retrofit",
]

IMS_GENERIC_PATTERNS = [
    r"ims\s+bearing\s+replaced",
    r"ims\s+replaced",
    r"ims\s+bearing\s+upgraded",
    r"ims\s+upgraded",
    r"new\s+ims",
    r"ims\s+done",
    r"imsb\s+replaced",
    r"ims\s+fix",
]

SIX_SPEED_PATTERNS = [
    # The 986 Boxster S only came in 6-speed manual or 5-speed Tiptronic. Once
    # we know it's a 986 S, "6 speed" / "6spd" / "6MT" all unambiguously mean
    # 6-speed manual — no need to require the "manual" word.
    r"\b6[-\s]?speed\b",
    r"\bsix[-\s]?speed\b",
    r"\b6\s*spd\b",
    r"\b6mt\b",
    r"6\s*speed\s+transaxle",
]

TIPTRONIC_PATTERNS = [
    r"tiptronic",
    r"5[-\s]speed\s+automatic",
    r"automatic\s+transmission",
]

FIVE_SPEED_PATTERNS = [
    r"5[-\s]speed\s+manual",
    r"five[-\s]speed\s+manual",
    r"\b5mt\b",
]

BOXSTER_S_PATTERNS = [
    r"boxster\s+s\b",
    r"986\s+s\b",
    r"3\.2l?\b",
    r"3\.2\s*liter",
    r"3\.2[-\s]liter",
]

BASE_BOXSTER_INDICATORS = [
    r"2\.7l?\b",
    r"2\.7\s*liter",
    r"base\s+boxster",
]


# ---------------------------------------------------------------------------
# Side effects — the legacy Listing fields we keep populating for backward compat
# ---------------------------------------------------------------------------


def _set_six_speed(listing):
    listing.transmission = "6-speed manual"


def _set_ims_solution(listing):
    listing.has_ims_solution = True


def _set_ims_retrofit(listing):
    listing.has_ims_retrofit = True


def _set_ims_replaced(listing):
    listing.has_ims_replaced = True


# ---------------------------------------------------------------------------
# Notion property builder — Boxster-specific schema mapping
# ---------------------------------------------------------------------------

# Canonical multi_select options — these match the options pre-created on the
# 986 Hunt database. Anything not in this set gets normalized via the helpers
# below before being sent to Notion (e.g. "📉 Low miles (47,500)" → "📉 Low miles").
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
    out: list[str] = []
    for flag in flags:
        if flag.startswith("❌"):
            continue
        if flag in _CANONICAL_FLAGS:
            out.append(flag)
        elif flag.startswith("📉 Low miles"):
            out.append("📉 Low miles")
        elif flag.startswith("✨ RARE"):
            out.append("✨ RARE")
        else:
            out.append(flag)
    return out


def _ims_status(listing: Listing) -> str:
    if listing.has_ims_solution:
        return "Solution"
    if listing.has_ims_retrofit:
        return "Retrofit"
    if listing.has_ims_replaced:
        return "Replaced (generic)"
    return "Unknown"


def _page_title(listing: Listing) -> str:
    year = listing.year or "????"
    color = (listing.color_match or {}).get("display") or listing.color_exterior or "Unknown"
    src = display_name(listing.source)
    return f"{year} {color} Boxster S — {src}"


def _build_notion_properties(listing: Listing) -> dict[str, Any]:
    title = _page_title(listing)
    color_category = (listing.color_match or {}).get("display")
    transmission = listing.transmission or "Unknown"
    flags = _normalize_flags(listing.flags)

    props: dict[str, Any] = {
        "Title": {"title": [{"text": {"content": title}}]},
        "Tier": {"select": {"name": listing.tier}},
        "Score": {"number": listing.score},
        "Source": {"select": {"name": display_name(listing.source)}},
        "Transmission": {"select": {"name": transmission}},
        "IMS Status": {"select": {"name": _ims_status(listing)}},
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


# ---------------------------------------------------------------------------
# Target definition
# ---------------------------------------------------------------------------

TARGET = TargetConfig(
    target_id="porsche_986_boxster_s",
    display_name="986 Boxster S Hunter",
    emoji="🏎️",
    title_keyword="boxster",
    year_range=(2003, 2004),
    disqualifiers=[
        Disqualifier(
            reason="❌ Base Boxster (not S)",
            patterns=BASE_BOXSTER_INDICATORS,
            require_absence=BOXSTER_S_PATTERNS,
        ),
        Disqualifier(
            reason="❌ Tiptronic transmission",
            patterns=TIPTRONIC_PATTERNS,
        ),
        Disqualifier(
            reason="❌ 5-speed manual (base Boxster)",
            patterns=FIVE_SPEED_PATTERNS,
            require_absence=SIX_SPEED_PATTERNS,
        ),
    ],
    positive_rules=[
        ScoringRule(
            points=30,
            flag="✅ 6-speed manual",
            patterns=SIX_SPEED_PATTERNS,
            side_effect=_set_six_speed,
            fallback_flag="⚠️ Transmission unclear — verify",
        ),
    ],
    tiered_rules=[
        TieredRule(
            tiers=[
                ScoringRule(
                    points=40,
                    flag="🏆 IMS Solution (permanent fix)",
                    patterns=IMS_SOLUTION_PATTERNS,
                    side_effect=_set_ims_solution,
                ),
                ScoringRule(
                    points=30,
                    flag="✅ IMS Retrofit",
                    patterns=IMS_RETROFIT_PATTERNS,
                    side_effect=_set_ims_retrofit,
                ),
                ScoringRule(
                    points=25,
                    flag="✅ IMS replaced (verify type)",
                    patterns=IMS_GENERIC_PATTERNS,
                    side_effect=_set_ims_replaced,
                ),
            ],
            fallback_flag="⚠️ IMS status unknown",
        ),
    ],
    colors=COLORS,
    low_mileage_threshold=50000,
    service_records_keywords=("service records", "maintenance history"),
    notion_database_id_env="NOTION_DATABASE_ID",
    slack_webhook_env="SLACK_WEBHOOK_URL",
    build_notion_properties=_build_notion_properties,
    notion_page_title=_page_title,
)
