"""Scoring engine. Takes a Listing, returns it with score, tier, and flags set."""

import re

from boxster_hunter.colors import match_color
from boxster_hunter.models import Listing

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
    # The 986 Boxster S only came in 6-speed manual or 5-speed Tiptronic. The
    # 5-speed manual was base-Boxster only and is filtered separately. Once
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


def _any_match(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def score_listing(listing: Listing) -> Listing:
    """Score a listing in place. Returns the same listing for chaining."""
    full_text = f"{listing.title} {listing.description}".lower()
    score = 0
    flags: list[str] = []

    # ---- DISQUALIFIERS ----
    is_s = _any_match(BOXSTER_S_PATTERNS, full_text)
    is_base = _any_match(BASE_BOXSTER_INDICATORS, full_text) and not is_s

    if is_base:
        return _reject(listing, "❌ Base Boxster (not S)")

    if _any_match(TIPTRONIC_PATTERNS, full_text):
        return _reject(listing, "❌ Tiptronic transmission")

    if _any_match(FIVE_SPEED_PATTERNS, full_text) and not _any_match(SIX_SPEED_PATTERNS, full_text):
        return _reject(listing, "❌ 5-speed manual (base Boxster)")

    if listing.year and listing.year not in (2003, 2004):
        return _reject(listing, f"❌ Wrong year ({listing.year})")

    # Forum scrapers pull from general "for sale" subforums where non-Boxsters
    # appear regularly (911s, Caymans, parts threads). Reject anything that
    # never mentions "boxster" anywhere in the text.
    if "boxster" not in full_text:
        return _reject(listing, "❌ Not a Boxster")

    # ---- POSITIVE SCORING ----

    # 6-speed manual (30 points)
    if _any_match(SIX_SPEED_PATTERNS, full_text):
        score += 30
        flags.append("✅ 6-speed manual")
        listing.transmission = "6-speed manual"
    else:
        flags.append("⚠️ Transmission unclear — verify")

    # IMS work (tiered: 40 / 30 / 25)
    if _any_match(IMS_SOLUTION_PATTERNS, full_text):
        score += 40
        flags.append("🏆 IMS Solution (permanent fix)")
        listing.has_ims_solution = True
    elif _any_match(IMS_RETROFIT_PATTERNS, full_text):
        score += 30
        flags.append("✅ IMS Retrofit")
        listing.has_ims_retrofit = True
    elif _any_match(IMS_GENERIC_PATTERNS, full_text):
        score += 25
        flags.append("✅ IMS replaced (verify type)")
        listing.has_ims_replaced = True
    else:
        flags.append("⚠️ IMS status unknown")

    # Color match (20 base + 10 rarity bonus). Match against the original-case
    # text so paint codes hit (codes are case-sensitive in the matcher).
    color_match = match_color(f"{listing.title} {listing.description}")
    if color_match:
        score += 20
        flags.append(f"{color_match['emoji']} {color_match['name']}")
        if color_match["rarity"] in ("rare", "very rare", "unicorn"):
            score += 10
            flags.append(f"✨ RARE: {color_match['rarity']}")
        listing.color_match = color_match

    # Service records bonus
    if "service records" in full_text or "maintenance history" in full_text:
        score += 5
        flags.append("📋 Service records mentioned")

    # Low mileage bonus
    if listing.mileage and listing.mileage < 50000:
        score += 5
        flags.append(f"📉 Low miles ({listing.mileage:,})")

    listing.score = score
    listing.tier = _tier_for(score)
    listing.flags = flags
    return listing


def _reject(listing: Listing, reason: str) -> Listing:
    listing.score = 0
    listing.tier = "REJECTED"
    listing.flags = [reason]
    return listing


def _tier_for(score: int) -> str:
    if score >= 90:
        return "🏆 GOLD"
    if score >= 70:
        return "🥇 STRONG"
    if score >= 50:
        return "🥈 REVIEW"
    return "🥉 MARGINAL"
