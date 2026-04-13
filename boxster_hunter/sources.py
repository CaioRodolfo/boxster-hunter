"""Source display names — used by the Notion sink and Slack notifier alike.

Kept in a tiny shared module so adding a new scraper requires touching only
one map (here) instead of two.
"""

SOURCE_DISPLAY: dict[str, str] = {
    "carsandbids": "Cars & Bids",
    "bringatrailer": "Bring a Trailer",
    "classic.com": "Classic.com",
    "craigslist": "Craigslist",
    "pcarmarket": "PCARMARKET",
    "986forum": "986forum",
    "rennlist": "Rennlist",
    "planet9": "Planet-9",
    "audiworld": "AudiWorld",
    "audizine": "AudiZine",
}


def display_name(source: str) -> str:
    return SOURCE_DISPLAY.get(source, source)
