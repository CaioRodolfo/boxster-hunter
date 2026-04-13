"""4th gen Toyota 4Runner target tests.

Verifies that the generic scoring engine produces the expected scores when
fed the 4Runner ``TargetConfig``. Mirrors test_target_audi_s3.py but for the
third target.
"""

from boxster_hunter.scoring import score_listing as _score_listing
from boxster_hunter.targets import TOYOTA_4RUNNER_4TH_GEN
from tests.conftest import make_listing


def score_4r(listing):
    return _score_listing(listing, TOYOTA_4RUNNER_4TH_GEN)


def _make_4r(year=2008, mileage=95000, **overrides):
    return make_listing(year=year, mileage=mileage, **overrides)


# ---------- Year preference ----------


def test_2008_2009_gets_top_year_bonus():
    listing = _make_4r(
        title="2009 Toyota 4Runner Sport Edition",
        description="Clean SUV, well-maintained.",
        year=2009,
    )
    scored = score_4r(listing)
    assert any("2008-2009" in f for f in scored.flags)


def test_2006_2007_gets_mid_year_bonus():
    listing = _make_4r(
        title="2007 Toyota 4Runner SR5",
        description="Original owner.",
        year=2007,
    )
    scored = score_4r(listing)
    assert any("2006-2007" in f for f in scored.flags)


def test_2003_2005_gets_baseline_year_bonus():
    listing = _make_4r(
        title="2004 Toyota 4Runner Limited V8",
        description="V8 engine, all original.",
        year=2004,
    )
    scored = score_4r(listing)
    assert any("2003-2005" in f for f in scored.flags)


def test_later_year_outranks_earlier():
    later = _make_4r(
        title="2009 Toyota 4Runner Limited",
        description="Pristine condition.",
        year=2009,
    )
    earlier = _make_4r(
        title="2003 Toyota 4Runner SR5",
        description="Pristine condition.",
        year=2003,
    )
    assert score_4r(later).score > score_4r(earlier).score


# ---------- Rust ----------


def test_explicit_rust_free_claim_scores_high():
    listing = _make_4r(
        title="2008 Toyota 4Runner Limited V8",
        description="Rust-free Arizona truck. Clean frame, never seen salt or snow.",
    )
    scored = score_4r(listing)
    assert any("Rust-free" in f for f in scored.flags)


def test_southern_provenance_fallback():
    listing = _make_4r(
        title="2007 Toyota 4Runner SR5",
        description="California car since new. Single owner.",
    )
    scored = score_4r(listing)
    assert any("Southern" in f for f in scored.flags)


def test_rust_warning_flagged_but_not_rejected():
    listing = _make_4r(
        title="2005 Toyota 4Runner SR5 V8",
        description="Some surface rust on the rear bumper, otherwise clean.",
    )
    scored = score_4r(listing)
    assert scored.tier != "REJECTED"
    assert any("Rust mentioned" in f for f in scored.flags)


def test_severe_rust_flagged_but_not_rejected():
    listing = _make_4r(
        title="2003 Toyota 4Runner Limited",
        description="Frame rotted out, needs frame replacement. Project car.",
    )
    scored = score_4r(listing)
    assert scored.tier != "REJECTED"
    assert any("Severe rust" in f for f in scored.flags)


# ---------- Timing service ----------


def test_timing_belt_replaced_scores():
    listing = _make_4r(
        title="2006 Toyota 4Runner Limited V8",
        description="Timing belt replaced at 95k miles. Water pump done at the same time.",
    )
    scored = score_4r(listing)
    assert any("Timing service" in f for f in scored.flags)


def test_90k_service_recognized_as_timing_service():
    listing = _make_4r(
        title="2007 Toyota 4Runner Limited V8",
        description="Just had the 90k mile service done at Toyota dealer.",
    )
    scored = score_4r(listing)
    assert any("Timing service" in f for f in scored.flags)


# ---------- Disqualifiers ----------


def test_reject_salvage_title():
    listing = _make_4r(
        title="2008 Toyota 4Runner Limited",
        description="Salvage title from a minor fender bender. Runs and drives.",
    )
    scored = score_4r(listing)
    assert scored.tier == "REJECTED"
    assert "Salvage" in scored.flags[0]


def test_reject_wrong_generation_3rd_gen():
    listing = _make_4r(
        title="2002 Toyota 4Runner",
        description="3rd gen SR5, automatic, V6.",
        year=2002,
    )
    scored = score_4r(listing)
    assert scored.tier == "REJECTED"


def test_reject_wrong_year_outside_range():
    listing = _make_4r(
        title="2010 Toyota 4Runner",
        description="Brand new 5th gen.",
        year=2010,
    )
    scored = score_4r(listing)
    assert scored.tier == "REJECTED"


def test_reject_non_4runner_listing():
    listing = _make_4r(
        title="2008 Toyota Tacoma",
        description="V6 manual, clean truck.",
    )
    scored = score_4r(listing)
    assert scored.tier == "REJECTED"


# ---------- Mileage ----------


def test_low_mileage_in_sweet_spot_gets_bonus():
    high = _make_4r(
        title="2008 Toyota 4Runner Limited V8",
        description="Solid truck.",
        mileage=130000,
    )
    low = _make_4r(
        title="2008 Toyota 4Runner Limited V8",
        description="Solid truck.",
        mileage=78000,
    )
    assert score_4r(low).score > score_4r(high).score


# ---------- Notion property builder ----------


def test_notion_property_builder_includes_4runner_specific_fields():
    listing = _make_4r(
        title="2008 Toyota 4Runner Limited V8",
        description=(
            "Rust-free Arizona truck since new. Clean frame, never seen salt. "
            "Timing belt replaced at 90k. Service records included. 92,000 miles."
        ),
        location="Phoenix, AZ",
        price=24500,
        mileage=92000,
    )
    scored = score_4r(listing)
    props = TOYOTA_4RUNNER_4TH_GEN.build_notion_properties(scored)
    assert props["Rust Status"]["select"]["name"] in ("Rust-free claimed", "Southern provenance")
    assert props["Provenance"]["select"]["name"] == "Southern/dry-climate"
    assert props["Timing Service"]["select"]["name"] == "Done"
    assert props["Year"]["number"] == 2008
    assert props["Price"]["number"] == 24500
    assert props["Mileage"]["number"] == 92000


def test_high_quality_listing_clears_review_threshold():
    """Sanity check: a listing that hits the year/rust/timing/mileage bonuses
    should clear the REVIEW threshold (50)."""
    listing = _make_4r(
        title="2009 Toyota 4Runner Limited V8",
        description=(
            "California car since new, rust-free with a clean frame. "
            "Timing belt replaced at 90k. Carfax shows full service history. "
            "92,000 miles."
        ),
        mileage=92000,
    )
    scored = score_4r(listing)
    assert scored.score >= 50
