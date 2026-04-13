"""Scoring engine tests. One fixture per tier; rejects covered separately."""

from boxster_hunter.scoring import score_listing as _score_listing
from boxster_hunter.targets import PORSCHE_986_BOXSTER_S
from tests.conftest import make_listing


def score_listing(listing):
    """Test alias: scores against the Boxster target. Phase 1 backward-compat."""
    return _score_listing(listing, PORSCHE_986_BOXSTER_S)


def test_gold_tier_ims_solution_six_speed_lagoon_green():
    listing = make_listing(
        title="2004 Porsche Boxster S — Lagoon Green Metallic, IMS Solution",
        description=(
            "6-speed manual, LN Engineering IMS Solution installed. "
            "Comprehensive service records. 47,500 miles."
        ),
        mileage=47500,
    )
    scored = score_listing(listing)
    assert scored.tier == "🏆 GOLD"
    assert scored.score >= 90
    assert scored.has_ims_solution is True
    assert scored.color_match["name"] == "Lagoon Green Metallic"
    assert scored.transmission == "6-speed manual"


def test_strong_tier_ims_replaced_six_speed_guards_red():
    listing = make_listing(
        title="2003 Porsche Boxster S",
        description="Guards Red over black, 6-speed manual, IMS bearing replaced last year.",
        year=2003,
        mileage=72000,
    )
    scored = score_listing(listing)
    assert scored.tier == "🥇 STRONG"
    assert 70 <= scored.score < 90


def test_review_tier_six_speed_generic_ims_no_color():
    # 6-speed (30) + generic IMS replaced (25) = 55 → REVIEW
    listing = make_listing(
        title="2004 Porsche Boxster S 3.2L",
        description="6-speed manual, Arctic Silver, IMS bearing replaced.",
    )
    scored = score_listing(listing)
    assert scored.tier == "🥈 REVIEW"
    assert 50 <= scored.score < 70


def test_marginal_tier_no_six_speed_no_ims_no_color():
    listing = make_listing(
        title="2004 Porsche Boxster S",
        description="3.2L, runs and drives.",
    )
    scored = score_listing(listing)
    assert scored.tier == "🥉 MARGINAL"
    assert scored.score < 50


def test_reject_tiptronic():
    listing = make_listing(
        title="2004 Porsche Boxster S",
        description="3.2L Tiptronic, low miles.",
    )
    scored = score_listing(listing)
    assert scored.tier == "REJECTED"
    assert "Tiptronic" in scored.flags[0]


def test_reject_base_boxster():
    listing = make_listing(
        title="2004 Porsche Boxster",
        description="Base Boxster, 2.7L, 5-speed manual.",
    )
    scored = score_listing(listing)
    assert scored.tier == "REJECTED"


def test_reject_five_speed_only():
    listing = make_listing(
        title="2003 Porsche Boxster",
        description="2.7 liter, 5-speed manual transmission.",
    )
    scored = score_listing(listing)
    assert scored.tier == "REJECTED"


def test_reject_wrong_year():
    listing = make_listing(
        title="2001 Porsche Boxster S",
        description="3.2L, 6-speed manual",
        year=2001,
    )
    scored = score_listing(listing)
    assert scored.tier == "REJECTED"
    assert "Wrong year" in scored.flags[0]


def test_rare_color_bonus():
    common = make_listing(
        title="2004 Boxster S — Guards Red",
        description="6-speed manual",
    )
    rare = make_listing(
        title="2004 Boxster S — Carmona Red Metallic",
        description="6-speed manual",
    )
    common_score = score_listing(common).score
    rare_score = score_listing(rare).score
    assert rare_score == common_score + 10


def test_ims_solution_outranks_retrofit():
    solution = score_listing(
        make_listing(
            title="2004 Boxster S",
            description="6-speed manual, IMS Solution installed",
        )
    ).score
    retrofit = score_listing(
        make_listing(
            title="2004 Boxster S",
            description="6-speed manual, IMS Retrofit installed",
        )
    ).score
    generic = score_listing(
        make_listing(
            title="2004 Boxster S",
            description="6-speed manual, IMS bearing replaced",
        )
    ).score
    assert solution > retrofit > generic


def test_six_speed_recognized_without_explicit_manual_word():
    """Sellers commonly write '6 speed' instead of '6-speed manual'."""
    cases = [
        "2004 Porsche Boxster S 3.2L, 6 speed, second owner",
        "2004 Boxster S, 3.2L, 6spd, low miles",
        "2003 Boxster S 3.2L six speed",
        "2003 Boxster S 6mt",
    ]
    for desc in cases:
        listing = make_listing(title="2004 Porsche Boxster S", description=desc)
        scored = score_listing(listing)
        assert any("6-speed" in f for f in scored.flags), f"missed: {desc!r}"


def test_low_mileage_bonus():
    high = score_listing(
        make_listing(
            title="2004 Boxster S 3.2L",
            description="6-speed manual",
            mileage=75000,
        )
    ).score
    low = score_listing(
        make_listing(
            title="2004 Boxster S 3.2L",
            description="6-speed manual",
            mileage=42000,
        )
    ).score
    assert low == high + 5
