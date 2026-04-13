"""Generic scoring engine.

This module is car-agnostic. It takes a ``TargetConfig`` and a ``Listing`` and
applies the target's disqualifiers, additive rules, tiered rules, color match,
and bonuses. To change *what* the system looks for, edit the relevant target
file under ``boxster_hunter/targets/``. Don't add patterns here.
"""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.targets.base import TargetConfig, any_match, match_color


def score_listing(listing: Listing, target: TargetConfig) -> Listing:
    """Score a listing in place against the given target. Returns the same listing."""
    full_text = f"{listing.title} {listing.description}".lower()

    # ---- Routing: must mention the target keyword somewhere ----
    if target.title_keyword not in full_text:
        return _reject(listing, f"❌ Not a {target.title_keyword}")

    # ---- Year filter ----
    if listing.year and not (target.year_range[0] <= listing.year <= target.year_range[1]):
        return _reject(listing, f"❌ Wrong year ({listing.year})")

    # ---- Disqualifiers ----
    for dq in target.disqualifiers:
        if any_match(dq.patterns, full_text):
            if dq.require_absence and any_match(dq.require_absence, full_text):
                continue
            return _reject(listing, dq.reason)

    score = 0
    flags: list[str] = []

    # ---- Additive positive rules ----
    for rule in target.positive_rules:
        if any_match(rule.patterns, full_text):
            score += rule.points
            flags.append(rule.flag)
            if rule.side_effect is not None:
                rule.side_effect(listing)
        elif rule.fallback_flag is not None:
            flags.append(rule.fallback_flag)

    # ---- Tiered rules: highest match wins ----
    for tiered in target.tiered_rules:
        matched = False
        for tier in tiered.tiers:
            if any_match(tier.patterns, full_text):
                score += tier.points
                flags.append(tier.flag)
                if tier.side_effect is not None:
                    tier.side_effect(listing)
                matched = True
                break
        if not matched and tiered.fallback_flag is not None:
            flags.append(tiered.fallback_flag)

    # ---- Color match ----
    color_match = match_color(f"{listing.title} {listing.description}", target.colors)
    if color_match:
        score += target.color_base_points
        flags.append(f"{color_match['emoji']} {color_match['name']}")
        if color_match["rarity"] in target.color_rarity_set:
            score += target.color_rarity_bonus
            flags.append(f"✨ RARE: {color_match['rarity']}")
        listing.color_match = color_match

    # ---- Service records bonus ----
    if target.service_records_keywords and any(
        kw in full_text for kw in target.service_records_keywords
    ):
        score += target.service_records_points
        flags.append("📋 Service records mentioned")

    # ---- Low mileage bonus ----
    if (
        target.low_mileage_threshold is not None
        and listing.mileage
        and listing.mileage < target.low_mileage_threshold
    ):
        score += target.low_mileage_points
        flags.append(f"📉 Low miles ({listing.mileage:,})")

    listing.score = score
    listing.tier = _tier_for(score, target)
    listing.flags = flags
    return listing


def _reject(listing: Listing, reason: str) -> Listing:
    listing.score = 0
    listing.tier = "REJECTED"
    listing.flags = [reason]
    return listing


def _tier_for(score: int, target: TargetConfig) -> str:
    gold, strong, review = target.tier_thresholds
    if score >= gold:
        return "🏆 GOLD"
    if score >= strong:
        return "🥇 STRONG"
    if score >= review:
        return "🥈 REVIEW"
    return "🥉 MARGINAL"
