"""Audi S3 8V facelift target — 2017-2020 US model years.

Scope:
  * 8V facelift only (mid-2016 through 2020 model years globally; US 2017-2020).
  * The next-gen 8Y (2022+) is a different car and gets caught by the year filter.
  * RS3 is excluded via disqualifier (different engine, different chassis tune).

What we score for:
  * Premium Plus or Prestige trim (the two "loaded" S3 trims; the base is just S3)
  * Bang & Olufsen sound system option
  * Documented Haldex maintenance (controller fluid + filter — service every 40k mi)
  * Other desirable boxes: APR / IE tune (modest bonus only — heavily modded cars
    score lower), DSG service, magnetic ride
  * "Cool" colors (no black/white/grey/silver). Audi Exclusive colors get the
    rare-color bonus.

Edit this file to tune. The scoring engine knows nothing about Audis.
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
# Colors — only 8V facelift offerings, excluding black/white/grey/Nardo
# ---------------------------------------------------------------------------

COLORS: dict[str, dict[str, Any]] = {
    "blue": {
        "display": "Blue",
        "emoji": "🔵",
        "variants": [
            {
                "name": "Sepang Blue Pearl Effect",
                "aliases": ["sepang blue", "sepang pearl"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "common",
            },
            {
                "name": "Ara Blue Crystal Effect",
                "aliases": ["ara blue", "ara crystal"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "uncommon",
            },
            {
                "name": "Cosmos Blue Metallic",
                "aliases": ["cosmos blue"],
                "codes": [],
                "years": [2017, 2018],
                "rarity": "rare",
            },
            {
                "name": "Nogaro Blue Pearl Effect",
                "aliases": ["nogaro blue", "nogaroblau"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "unicorn",  # Audi Exclusive paint-to-sample
            },
        ],
    },
    "red": {
        "display": "Red",
        "emoji": "❤️",
        "variants": [
            {
                "name": "Misano Red Pearl Effect",
                "aliases": ["misano red", "misano pearl"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "common",
            },
            {
                "name": "Tango Red Metallic",
                "aliases": ["tango red", "tangorot"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "uncommon",
            },
            {
                "name": "Catalunya Red Pearl Effect",
                "aliases": ["catalunya red", "catalunya pearl"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "unicorn",  # Audi Exclusive
            },
        ],
    },
    "yellow": {
        "display": "Yellow",
        "emoji": "💛",
        "variants": [
            {
                "name": "Vegas Yellow",
                "aliases": ["vegas yellow", "vegas gelb"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "unicorn",  # Audi Exclusive
            },
        ],
    },
    "orange": {
        "display": "Orange",
        "emoji": "🧡",
        "variants": [
            {
                "name": "Solar Orange",
                "aliases": ["solar orange"],
                "codes": [],
                "years": [2017, 2018, 2019, 2020],
                "rarity": "unicorn",  # Audi Exclusive
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Pattern banks
# ---------------------------------------------------------------------------

# Trim level — Premium Plus and Prestige are the desirable two
PREMIUM_PLUS_PATTERNS = [
    r"premium\s*plus",
    r"\bp\+\b",
    r"\bpremium\s*\+\b",
]

PRESTIGE_PATTERNS = [
    r"\bprestige\b",
]

# Sound system — Bang & Olufsen is the option we want
BANG_OLUFSEN_PATTERNS = [
    r"bang\s*&?\s*olufsen",
    r"\bb\s*&\s*o\b",
    r"\bb\s*and\s*o\b",
    r"\bbo\s+sound",
    r"\bb&o\b",
]

# Haldex maintenance — fluid + filter service is the AWD differential treatment
HALDEX_PATTERNS = [
    r"haldex\s+(fluid|service|filter)",
    r"haldex\s+(replaced|changed|done|maintenance)",
    r"awd\s+service",
    r"awd\s+fluid",
    r"haldex\s+coupler",
]

# Transmission — 8V S3 only came with a 7-speed S-Tronic dual-clutch (DSG)
S_TRONIC_PATTERNS = [
    r"s[-\s]?tronic",
    r"\bdsg\b",
    r"7[-\s]?speed",
    r"dual[-\s]clutch",
    r"\bdct\b",
]

# Disqualifiers — wrong cars
RS3_PATTERNS = [
    r"\brs\s*3\b",
    r"\brs3\b",
]

A3_BASE_PATTERNS = [
    # Base A3 (not S3) — caught by absence of "S3"
    r"\ba3\s+(premium|sportback|sedan)",
    r"audi\s+a3\s",
]

# What identifies an S3 — used for "must mention" check + disambiguation
S3_INDICATORS = [
    r"\baudi\s+s3\b",
    r"\bs3\s+sedan\b",
    r"\bs3\s+premium\b",
    r"\bs3\s+prestige\b",
    r"8v\s+s3",
    r"\bs3\b",
]


# ---------------------------------------------------------------------------
# Side effects
# ---------------------------------------------------------------------------


def _set_premium_plus(listing: Listing) -> None:
    listing.trim = "Premium Plus"


def _set_prestige(listing: Listing) -> None:
    listing.trim = "Prestige"


def _set_s_tronic(listing: Listing) -> None:
    listing.transmission = "7-speed S-Tronic"


# ---------------------------------------------------------------------------
# Notion property builder
# ---------------------------------------------------------------------------

_CANONICAL_FLAGS = {
    "🥇 Prestige trim",
    "✅ Premium Plus trim",
    "🎵 Bang & Olufsen sound",
    "🔧 Haldex service documented",
    "✅ 7-speed S-Tronic",
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


def _trim_for_notion(listing: Listing) -> str:
    return listing.trim or "Unknown"


def _bo_sound_for_notion(listing: Listing) -> str:
    if any("Bang & Olufsen" in f for f in listing.flags):
        return "Yes"
    return "Unknown"


def _haldex_for_notion(listing: Listing) -> str:
    if any("Haldex" in f for f in listing.flags):
        return "Documented"
    return "Unknown"


def _page_title(listing: Listing) -> str:
    year = listing.year or "????"
    color = (listing.color_match or {}).get("display") or listing.color_exterior or "Unknown"
    src = display_name(listing.source)
    return f"{year} {color} Audi S3 — {src}"


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
        "Trim": {"select": {"name": _trim_for_notion(listing)}},
        "B&O Sound": {"select": {"name": _bo_sound_for_notion(listing)}},
        "Haldex Service": {"select": {"name": _haldex_for_notion(listing)}},
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
    if flags:
        props["Flags"] = {"multi_select": [{"name": f} for f in flags]}

    return props


# ---------------------------------------------------------------------------
# Target definition
# ---------------------------------------------------------------------------

TARGET = TargetConfig(
    target_id="audi_s3_8v_facelift",
    display_name="Audi S3 8V Facelift Hunter",
    emoji="🏁",
    title_keyword="s3",
    year_range=(2017, 2020),
    disqualifiers=[
        Disqualifier(
            reason="❌ RS3 (different car)",
            patterns=RS3_PATTERNS,
        ),
        Disqualifier(
            reason="❌ Base A3 (not S3)",
            patterns=A3_BASE_PATTERNS,
            require_absence=S3_INDICATORS,
        ),
    ],
    positive_rules=[
        ScoringRule(
            points=20,
            flag="🎵 Bang & Olufsen sound",
            patterns=BANG_OLUFSEN_PATTERNS,
        ),
        ScoringRule(
            points=15,
            flag="🔧 Haldex service documented",
            patterns=HALDEX_PATTERNS,
        ),
        ScoringRule(
            points=10,
            flag="✅ 7-speed S-Tronic",
            patterns=S_TRONIC_PATTERNS,
            side_effect=_set_s_tronic,
        ),
    ],
    tiered_rules=[
        TieredRule(
            tiers=[
                ScoringRule(
                    points=25,
                    flag="🥇 Prestige trim",
                    patterns=PRESTIGE_PATTERNS,
                    side_effect=_set_prestige,
                ),
                ScoringRule(
                    points=20,
                    flag="✅ Premium Plus trim",
                    patterns=PREMIUM_PLUS_PATTERNS,
                    side_effect=_set_premium_plus,
                ),
            ],
            fallback_flag="⚠️ Trim unknown — likely base S3",
        ),
    ],
    colors=COLORS,
    color_base_points=20,
    color_rarity_bonus=15,  # Audi Exclusive colors are very rare
    low_mileage_threshold=60000,  # 8V S3s are 5-8 years old; <60k is uncommon
    service_records_keywords=("service records", "maintenance history", "carfax"),
    notion_database_id_env="NOTION_DATABASE_ID_S3",
    slack_webhook_env="SLACK_WEBHOOK_URL_S3",
    build_notion_properties=_build_notion_properties,
    notion_page_title=_page_title,
)
