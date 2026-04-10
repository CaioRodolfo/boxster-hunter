"""Target paint colors for a 2003-2004 Porsche 986 Boxster S.

Paint codes sourced from RennTech.org External Paint Colors database.
Only colors available on the 2003-2004 model years are included.
"""

from typing import Any

TARGET_COLORS: dict[str, dict[str, Any]] = {
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


def match_color(listing_text: str) -> dict[str, Any] | None:
    """Return the first matching target color for a listing, or None.

    Aliases are matched case-insensitively against the full text. Paint codes
    are matched exact-case against the original text so we don't grab a stray
    "12H" out of an unrelated phrase.
    """
    text_lower = listing_text.lower()
    for category, data in TARGET_COLORS.items():
        for variant in data["variants"]:
            for alias in variant["aliases"]:
                if alias in text_lower:
                    return _match_dict(category, data, variant, "alias")
            for code in variant["codes"]:
                if code in listing_text:
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
