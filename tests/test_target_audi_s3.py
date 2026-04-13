"""Audi S3 8V facelift target tests.

Verifies that the generic scoring engine produces the expected scores when
fed the S3 ``TargetConfig``. Mirrors test_scoring.py but for the second
target. These tests are the regression suite for the multi-target refactor —
if the engine works for both Boxster and S3, the abstraction is sound.
"""

from boxster_hunter.scoring import score_listing as _score_listing
from boxster_hunter.targets import AUDI_S3_8V_FACELIFT
from tests.conftest import make_listing


def score_s3(listing):
    return _score_listing(listing, AUDI_S3_8V_FACELIFT)


def _make_s3(year=2018, mileage=42000, **overrides):
    return make_listing(year=year, mileage=mileage, **overrides)


def test_gold_tier_loaded_prestige_b_and_o_haldex_misano():
    listing = _make_s3(
        title="2018 Audi S3 Prestige — Misano Red",
        description=(
            "Prestige trim with the Bang & Olufsen sound system, magnetic ride, "
            "virtual cockpit, and the technology package. 7-speed S-Tronic. "
            "Misano Red Pearl Effect over black leather. Haldex fluid and "
            "filter service done at 35k miles. Comprehensive service records "
            "and clean Carfax. 42,500 miles."
        ),
        mileage=42500,
    )
    scored = score_s3(listing)
    assert scored.tier in ("🏆 GOLD", "🥇 STRONG")
    assert scored.score >= 70


def test_strong_tier_premium_plus_no_haldex_no_color():
    listing = _make_s3(
        title="2019 Audi S3 Premium Plus",
        description=(
            "Premium Plus trim, B&O sound, 7-speed dual-clutch, Daytona Grey, "
            "single owner, dealer maintained, full service records."
        ),
    )
    scored = score_s3(listing)
    # Premium Plus 20 + B&O 20 + S-Tronic 10 + service records 5 + low miles 5 = 60
    assert scored.score >= 50
    assert scored.tier in ("🥈 REVIEW", "🥇 STRONG")


def test_reject_rs3():
    listing = _make_s3(
        title="2018 Audi RS3 Sedan — Nardo Grey",
        description="Stock RS3 with the 2.5L 5-cylinder. DSG. 35k miles.",
    )
    scored = score_s3(listing)
    assert scored.tier == "REJECTED"
    assert "RS3" in scored.flags[0]


def test_reject_base_a3():
    listing = _make_s3(
        title="2018 Audi A3 Premium",
        description="Base 2.0T A3, FWD, S-Tronic, Brilliant Black.",
    )
    scored = score_s3(listing)
    assert scored.tier == "REJECTED"


def test_reject_wrong_year_8y_generation():
    listing = _make_s3(
        title="2023 Audi S3 Premium Plus",
        description="Brand new 8Y generation. B&O sound, S-Tronic.",
        year=2023,
    )
    scored = score_s3(listing)
    assert scored.tier == "REJECTED"
    assert "Wrong year" in scored.flags[0]


def test_color_match_misano_red():
    listing = _make_s3(
        title="2018 Audi S3 — Misano Red Pearl Effect",
        description="7-speed S-Tronic, premium plus, Misano Red.",
    )
    scored = score_s3(listing)
    assert scored.color_match is not None
    assert scored.color_match["name"] == "Misano Red Pearl Effect"


def test_color_match_audi_exclusive_unicorn_gets_rare_bonus():
    common = _make_s3(
        title="2018 Audi S3 Misano Red",
        description="7-speed S-Tronic, Premium Plus.",
    )
    unicorn = _make_s3(
        title="2018 Audi S3 Nogaro Blue",
        description="7-speed S-Tronic, Premium Plus.",
    )
    common_score = score_s3(common).score
    unicorn_score = score_s3(unicorn).score
    # Audi Exclusive paint should add the rarity bonus
    assert unicorn_score > common_score


def test_haldex_documented_adds_points():
    no_haldex = _make_s3(
        title="2018 Audi S3 Premium Plus",
        description="7-speed S-Tronic, Premium Plus, single owner.",
    )
    with_haldex = _make_s3(
        title="2018 Audi S3 Premium Plus",
        description="7-speed S-Tronic, Premium Plus, single owner. Haldex fluid replaced at 30k.",
    )
    assert score_s3(with_haldex).score > score_s3(no_haldex).score


def test_b_and_o_detected_via_multiple_aliases():
    aliases = [
        "Bang & Olufsen sound system",
        "B&O speakers",
        "B & O premium audio",
    ]
    for alias in aliases:
        listing = _make_s3(
            title="2018 Audi S3 Premium Plus",
            description=f"7-speed S-Tronic, Premium Plus. {alias}.",
        )
        scored = score_s3(listing)
        assert any("Bang & Olufsen" in f for f in scored.flags), f"missed alias: {alias!r}"


def test_prestige_outranks_premium_plus():
    pp = _make_s3(
        title="2018 Audi S3",
        description="Premium Plus, 7-speed S-Tronic.",
    )
    pr = _make_s3(
        title="2018 Audi S3",
        description="Prestige trim, 7-speed S-Tronic.",
    )
    pp_score = score_s3(pp).score
    pr_score = score_s3(pr).score
    assert pr_score > pp_score


def test_reject_non_s3_listing():
    listing = _make_s3(
        title="2018 Porsche Boxster S",
        description="6-speed manual.",
    )
    scored = score_s3(listing)
    assert scored.tier == "REJECTED"


def test_notion_property_builder_includes_audi_specific_fields():
    listing = _make_s3(
        title="2018 Audi S3 Prestige — Misano Red",
        description=(
            "Prestige trim. Bang & Olufsen sound. 7-speed S-Tronic. Misano Red. "
            "Haldex service done. Service records included."
        ),
        location="Brooklyn, NY",
        price=32000,
    )
    scored = score_s3(listing)
    props = AUDI_S3_8V_FACELIFT.build_notion_properties(scored)
    assert props["Trim"]["select"]["name"] == "Prestige"
    assert props["B&O Sound"]["select"]["name"] == "Yes"
    assert props["Haldex Service"]["select"]["name"] == "Documented"
    assert props["Color"]["select"]["name"] == "Red"
    assert props["Year"]["number"] == 2018
    assert props["Price"]["number"] == 32000
