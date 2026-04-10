"""Color matcher tests. Every target variant should match; false positives should not."""

import pytest

from boxster_hunter.colors import TARGET_COLORS, match_color


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("Beautiful Lagoon Green Metallic example", "Lagoon Green Metallic"),
        ("paint code M6W on the door jamb", "Lagoon Green Metallic"),
        ("Pine Green looking sharp", "Pine Green Metallic"),
        ("rare 2B4 paint", "Pine Green Metallic"),
        ("Speed Yellow over black", "Speed Yellow"),
        ("Fayence Yellow unicorn car", "Fayence Yellow"),
        ("LAPIS BLUE / sand beige", "Lapis Blue Metallic"),
        ("Cobalt Blue Metallic, manual", "Cobalt Blue Metallic"),
        ("midnight blue with grey leather", "Midnight Blue Metallic"),
        ("Guards Red, classic look", "Guards Red"),
        ("Orient Red Metallic — gorgeous", "Orient Red Metallic"),
        ("Carmona Red, super rare", "Carmona Red Metallic"),
    ],
)
def test_match_color_hits(text, expected_name):
    result = match_color(text)
    assert result is not None
    assert result["name"] == expected_name


@pytest.mark.parametrize(
    "text",
    [
        "Arctic Silver Metallic",
        "black on black",
        "seal grey",
        "white with red interior",
        "",
    ],
)
def test_match_color_misses(text):
    assert match_color(text) is None


def test_paint_code_is_case_sensitive():
    # Lowercase 'm6w' should NOT match (codes are case-sensitive on purpose)
    assert match_color("paint code m6w") is None
    assert match_color("paint code M6W") is not None


def test_rarity_levels_present():
    # Sanity-check that the rarity field on every variant is one of our known buckets
    valid = {"common", "uncommon", "rare", "very rare", "unicorn"}
    for category in TARGET_COLORS.values():
        for variant in category["variants"]:
            assert variant["rarity"] in valid
