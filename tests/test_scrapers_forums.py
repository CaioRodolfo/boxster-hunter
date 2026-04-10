"""Parser tests for the Phase 4 forum scrapers."""

from pathlib import Path

from boxster_hunter.scoring import score_listing
from boxster_hunter.scrapers.boxster_forum import BoxsterForumScraper
from boxster_hunter.scrapers.pcarmarket import PCarMarketScraper
from boxster_hunter.scrapers.planet9 import Planet9Scraper
from boxster_hunter.scrapers.rennlist import RennlistScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load(rel: str) -> str:
    return (FIXTURES / rel).read_text()


# ---------- PCARMARKET ----------

def test_pcarmarket_parses_two_cards():
    listings = PCarMarketScraper().parse(_load("pcarmarket/search.html"))
    assert len(listings) == 2


def test_pcarmarket_midnight_blue_is_gold():
    listings = PCarMarketScraper().parse(_load("pcarmarket/search.html"))
    midnight = next(item for item in listings if "Midnight" in item.title)
    scored = score_listing(midnight)
    assert scored.tier == "🏆 GOLD"
    assert scored.has_ims_solution is True


def test_pcarmarket_extracts_price_and_mileage():
    listings = PCarMarketScraper().parse(_load("pcarmarket/search.html"))
    midnight = next(item for item in listings if "Midnight" in item.title)
    assert midnight.price == 23500
    assert midnight.mileage == 38500
    assert midnight.location == "Seattle, WA"


# ---------- 986forum ----------

def test_boxster_forum_parses_two_threads():
    listings = BoxsterForumScraper().parse(_load("boxster_forum/forsale.html"))
    assert len(listings) == 2


def test_boxster_forum_lagoon_green_is_gold():
    listings = BoxsterForumScraper().parse(_load("boxster_forum/forsale.html"))
    lagoon = next(item for item in listings if "Lagoon" in item.title)
    scored = score_listing(lagoon)
    assert scored.tier == "🏆 GOLD"
    assert scored.color_match["name"] == "Lagoon Green Metallic"


def test_boxster_forum_tiptronic_rejected():
    listings = BoxsterForumScraper().parse(_load("boxster_forum/forsale.html"))
    tip = next(item for item in listings if "Tiptronic" in item.title)
    scored = score_listing(tip)
    assert scored.tier == "REJECTED"


# ---------- Rennlist ----------

def test_rennlist_pine_green_strong_or_gold():
    listings = RennlistScraper().parse(_load("rennlist/classifieds.html"))
    pine = next(item for item in listings if "Pine" in item.title)
    scored = score_listing(pine)
    assert scored.score >= 70


def test_rennlist_base_5mt_rejected():
    listings = RennlistScraper().parse(_load("rennlist/classifieds.html"))
    base = next(item for item in listings if "5MT" in item.title or "base" in item.title.lower())
    scored = score_listing(base)
    assert scored.tier == "REJECTED"


# ---------- Planet-9 ----------

def test_planet9_fayence_yellow_is_gold():
    listings = Planet9Scraper().parse(_load("planet9/forsale.html"))
    fayence = next(item for item in listings if "Fayence" in item.title)
    scored = score_listing(fayence)
    assert scored.tier == "🏆 GOLD"
    # Fayence Yellow is "unicorn" rarity → should hit the rare bonus
    assert scored.color_match["rarity"] == "unicorn"
    assert any("RARE" in f for f in scored.flags)


def test_planet9_silver_is_below_gold():
    listings = Planet9Scraper().parse(_load("planet9/forsale.html"))
    silver = next(item for item in listings if "Arctic" in item.title)
    scored = score_listing(silver)
    assert scored.tier != "🏆 GOLD"
