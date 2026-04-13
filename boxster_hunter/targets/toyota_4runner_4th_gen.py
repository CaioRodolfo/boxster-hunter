"""4th gen Toyota 4Runner target — 2003-2009 model years.

Hunts the 4th gen 4Runner with these priorities:

  * Year preference: graduated bonus, later years preferred (2008-09 best,
    2006-07 next, 2003-05 baseline).
  * Mileage sweet spot: 60k-140k. Below 60k is suspicious (rare for a 20+
    year old SUV — could be clocked or a garage queen with deferred
    maintenance), above 140k is too much. Within the band, lower is better.
  * Rust: scored heavily as a positive when the listing explicitly claims
    rust-free, with a southern-state provenance bonus as a fallback signal
    when no rust claim is made. Frame rust mentions get a warning flag but
    are NOT auto-rejected — the user can decide from the flag whether to
    follow up.
  * Timing service: any mention of timing belt/chain work or "90k service"
    earns a bonus. The V8 (2UZ-FE) needs a timing belt at ~90k miles; the
    V6 (1GR-FE) has a chain that's maintenance-free, but a seller mentioning
    timing work on either engine is a positive signal.

Edit this file to tune. The scoring engine knows nothing about Toyotas.
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
# Pattern banks
# ---------------------------------------------------------------------------

# Graduated year preference. The patterns target the year as it appears in
# the listing title — Cars & Bids / BaT / Classic.com all put the year first.
LATE_YEAR_PATTERNS = [r"\b200[89]\b"]   # 2008-2009 — best of the gen
MID_YEAR_PATTERNS = [r"\b200[67]\b"]    # 2006-2007 — refresh + V8 mature
EARLY_YEAR_PATTERNS = [r"\b200[345]\b"] # 2003-2005 — baseline, still fine

# Timing service — both engines, any phrasing
TIMING_SERVICE_PATTERNS = [
    r"timing\s+belt\s+(replaced|done|new|service|kit)",
    r"timing\s+chain\s+(replaced|done|new|service)",
    r"new\s+timing\s+belt",
    r"new\s+timing\s+chain",
    r"\b90[k,]?\s*(mile|mi|k)\s+service",
    r"\b90[,]?000\s+(mile|mi)\s+service",
    r"timing\s+service\s+done",
    r"timing\s+kit\s+(installed|done|replaced)",
]

# Explicit rust-free claims (strongest positive signal)
RUST_FREE_PATTERNS = [
    r"\brust[-\s]free\b",
    r"\bno\s+rust\b",
    r"\bzero\s+rust\b",
    r"\bclean\s+frame\b",
    r"\bsolid\s+frame\b",
    r"\bpristine\s+frame\b",
    r"\bnever\s+rusted\b",
    r"\bnever\s+seen\s+(rust|salt|snow|winter)\b",
    r"\bno\s+frame\s+rust\b",
    r"\bsalt[-\s]free\b",
]

# Southern / dry-climate provenance — fallback when no explicit rust claim.
# Matches a southern state name in any vehicle context: "{state} car",
# "{state} truck", "{state} suv", "{state} kept|owned|since new", and the
# generic "located in {state}" / "from {state}". Also covers state
# abbreviations after a context word ("AZ truck", "located in CA").
# Risk: a listing that mentions an unrelated southern destination ("road trip
# from California to NY") might false-positive — but that's rare in for-sale
# threads and the bonus is only +15, not a hard reject.
_SOUTHERN_STATES = (
    r"california|arizona|texas|nevada|new\s+mexico|florida|georgia|"
    r"south\s+carolina|alabama|tennessee|oklahoma|louisiana|utah|hawaii"
)
_SOUTHERN_ABBREVS = r"ca|az|tx|nv|nm|fl|ga|sc|al|tn|ok|la|ut|hi"

SOUTHERN_PROVENANCE_PATTERNS = [
    rf"\b({_SOUTHERN_STATES})\s+(car|truck|suv|kept|owned|since\s+new|its\s+entire\s+life)\b",
    rf"\b({_SOUTHERN_ABBREVS})\s+(car|truck|suv|kept|owned)\b",
    rf"\b(located\s+in|from|originally\s+(from|in))\s+({_SOUTHERN_STATES})\b",
    r"\bsouthern\s+(car|kept|owned|truck|suv)\b",
    r"\bdesert\s+(car|truck|suv|kept|southwest)\b",
    r"\bsouthwest\s+(car|kept|truck|suv)\b",
    r"\bsouth[-\s]west\s+kept\b",
    r"\bsocal\b",
    r"\bnocal\b",
    r"\bbay\s+area\s+(car|truck|kept)\b",
]

# Rust warnings — flag but don't reject. Surface rust on a 20-year-old SUV
# is normal and not necessarily disqualifying.
RUST_WARNING_PATTERNS = [
    r"\bsurface\s+rust\b",
    r"\bsome\s+rust\b",
    r"\bminor\s+rust\b",
    r"\bframe\s+rust\b",
    r"\brust\s+(repair|repaired|remediation)\b",
    r"\bunderbody\s+rust\b",
    r"\brusty\s+frame\b",
]

# Severe rust — these still don't auto-reject because some buyers are OK
# with frame replacement, but they get a strong warning flag.
SEVERE_RUST_PATTERNS = [
    r"\bframe\s+(rot|rotted|gone|swiss\s+cheese)\b",
    r"\bperforation\b",
    r"\brusted\s+through\b",
    r"\bframe\s+replacement\b",
]

# Salvage / rebuilt title — same as Boxster
SALVAGE_TITLE_PATTERNS = [
    r"\bsalvage\s+title\b",
    r"\brebuilt\s+title\b",
    r"\bbranded\s+title\b",
    r"\bflood\s+(title|damage)\b",
]

# Wrong-generation disqualifiers. The 4th gen is 2003-2009; everything else
# is a different car. We also catch 2-digit year prefixes that show up in
# forum titles ("85 4runner", "97 4runner") because the global year extractor
# only handles 4-digit years and would otherwise leave listing.year as None,
# bypassing the year-range filter.
WRONG_GENERATION_TITLE_PATTERNS = [
    r"\b1st\s+gen\b",
    r"\bfirst\s+gen\b",
    r"\b2nd\s+gen\b",
    r"\bsecond\s+gen\b",
    r"\b3rd\s+gen\b",
    r"\bthird\s+gen\b",
    r"\b5th\s+gen\b",
    r"\bfifth\s+gen\b",
    r"\b6th\s+gen\b",
    r"\bsixth\s+gen\b",
    # Pre-2003 model year as 2-digit prefix
    r"\b'?[89]\d\s+4runner\b",
    r"\b'?[89]\d\s*'?\s+4runner\b",
    # 2010+ model year as 4-digit prefix
    r"\b201[0-9]\s+4runner\b",
    r"\b202[0-9]\s+4runner\b",
]


# ---------------------------------------------------------------------------
# Notion property builder
# ---------------------------------------------------------------------------

_CANONICAL_FLAGS = {
    "🏆 2008-2009 (best of gen)",
    "✅ 2006-2007",
    "✅ 2003-2005",
    "🛡️ Rust-free claimed",
    "☀️ Southern/dry-climate provenance",
    "🔧 Timing service done",
    "📋 Service records mentioned",
    "📉 Sweet spot mileage",
    "⚠️ Rust mentioned",
    "🚨 Severe rust mentioned",
}


def _normalize_flags(flags: list[str]) -> list[str]:
    out: list[str] = []
    for flag in flags:
        if flag.startswith("❌"):
            continue
        if flag in _CANONICAL_FLAGS:
            out.append(flag)
        elif flag.startswith("📉 Sweet spot"):
            out.append("📉 Sweet spot mileage")
        elif flag.startswith("⚠️ Rust"):
            out.append("⚠️ Rust mentioned")
        elif flag.startswith("🚨"):
            out.append("🚨 Severe rust mentioned")
        else:
            out.append(flag)
    return out


def _rust_status_for_notion(listing: Listing) -> str:
    if any("Rust-free claimed" in f for f in listing.flags):
        return "Rust-free claimed"
    if any("Severe rust" in f for f in listing.flags):
        return "Severe rust mentioned"
    if any("Rust mentioned" in f for f in listing.flags):
        return "Rust mentioned"
    if any("Southern" in f for f in listing.flags):
        return "Southern provenance"
    return "Unknown"


def _provenance_for_notion(listing: Listing) -> str:
    if any("Southern" in f for f in listing.flags):
        return "Southern/dry-climate"
    return "Unknown"


def _timing_for_notion(listing: Listing) -> str:
    if any("Timing service" in f for f in listing.flags):
        return "Done"
    return "Unknown"


def _page_title(listing: Listing) -> str:
    year = listing.year or "????"
    src = display_name(listing.source)
    return f"{year} Toyota 4Runner — {src}"


def _build_notion_properties(listing: Listing) -> dict[str, Any]:
    title = _page_title(listing)
    flags = _normalize_flags(listing.flags)

    props: dict[str, Any] = {
        "Title": {"title": [{"text": {"content": title}}]},
        "Tier": {"select": {"name": listing.tier}},
        "Score": {"number": listing.score},
        "Source": {"select": {"name": display_name(listing.source)}},
        "Rust Status": {"select": {"name": _rust_status_for_notion(listing)}},
        "Provenance": {"select": {"name": _provenance_for_notion(listing)}},
        "Timing Service": {"select": {"name": _timing_for_notion(listing)}},
        "URL": {"url": listing.url_str},
        "First Seen": {"date": {"start": listing.first_seen.isoformat()}},
    }

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
    target_id="toyota_4runner_4th_gen",
    display_name="4th Gen 4Runner Hunter",
    emoji="🛻",
    title_keyword="4runner",
    year_range=(2003, 2009),
    disqualifiers=[
        Disqualifier(
            reason="❌ Salvage / rebuilt title",
            patterns=SALVAGE_TITLE_PATTERNS,
        ),
        Disqualifier(
            reason="❌ Wrong generation (3rd or 5th gen)",
            patterns=WRONG_GENERATION_TITLE_PATTERNS,
        ),
    ],
    positive_rules=[
        ScoringRule(
            points=20,
            flag="🛡️ Rust-free claimed",
            patterns=RUST_FREE_PATTERNS,
        ),
        ScoringRule(
            points=15,
            flag="☀️ Southern/dry-climate provenance",
            patterns=SOUTHERN_PROVENANCE_PATTERNS,
        ),
        ScoringRule(
            points=20,
            flag="🔧 Timing service done",
            patterns=TIMING_SERVICE_PATTERNS,
        ),
        ScoringRule(
            points=0,
            flag="⚠️ Rust mentioned — check listing",
            patterns=RUST_WARNING_PATTERNS,
        ),
        ScoringRule(
            points=0,
            flag="🚨 Severe rust mentioned — likely needs frame work",
            patterns=SEVERE_RUST_PATTERNS,
        ),
    ],
    tiered_rules=[
        # Graduated year preference. Tiered so we award each listing the
        # *best* matching tier (later years win when titles overlap, which
        # they shouldn't but the engine handles it cleanly).
        TieredRule(
            tiers=[
                ScoringRule(
                    points=15,
                    flag="🏆 2008-2009 (best of gen)",
                    patterns=LATE_YEAR_PATTERNS,
                ),
                ScoringRule(
                    points=10,
                    flag="✅ 2006-2007",
                    patterns=MID_YEAR_PATTERNS,
                ),
                ScoringRule(
                    points=5,
                    flag="✅ 2003-2005",
                    patterns=EARLY_YEAR_PATTERNS,
                ),
            ],
        ),
    ],
    colors={},  # 4Runner colors are not part of the spec
    # Sweet-spot mileage band: the spec says 60k-140k. Anything under 100k
    # within that band gets the bonus; the engine's threshold is "less than
    # this number, give the bonus". We use 100k so the lower half of the
    # band is rewarded but the upper half (100k-140k) still surfaces.
    low_mileage_threshold=100000,
    low_mileage_points=10,
    service_records_keywords=("service records", "maintenance history", "carfax", "service history"),
    service_records_points=5,
    notion_database_id_env="NOTION_DATABASE_ID_4RUNNER",
    slack_webhook_env="SLACK_WEBHOOK_URL_4RUNNER",
    build_notion_properties=_build_notion_properties,
    notion_page_title=_page_title,
    # Lowered REVIEW threshold to 0 for the 4Runner hunt: rust / timing /
    # provenance signals are often missing from listings even on solid cars,
    # and the user wants every non-rejected 4Runner pushed to Slack so they
    # can decide manually. Threshold 0 means any listing that survives the
    # disqualifier filter (year, generation, salvage title) becomes REVIEW —
    # the only thing that stays silent is a REJECTED listing.
    tier_thresholds=(90, 70, 0),
)
