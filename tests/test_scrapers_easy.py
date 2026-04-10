"""Parser tests for the Phase 2 scrapers (Cars & Bids, Classic.com, Craigslist).

Tests run against committed fixtures only — no live HTTP. We test parse() in
isolation; fetch_listings() is exercised in the integration test with mocked
responses.
"""

from pathlib import Path

from boxster_hunter.scoring import score_listing
from boxster_hunter.scrapers.carsandbids import CarsAndBidsScraper
from boxster_hunter.scrapers.classic_dot_com import ClassicDotComScraper
from boxster_hunter.scrapers.craigslist import CraigslistScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load(rel: str) -> str:
    return (FIXTURES / rel).read_text()


# ---------- Cars & Bids ----------

def test_carsandbids_parses_three_listings():
    listings = CarsAndBidsScraper().parse(_load("carsandbids/search.json"))
    assert len(listings) == 3


def test_carsandbids_first_listing_is_gold_after_scoring():
    listings = CarsAndBidsScraper().parse(_load("carsandbids/search.json"))
    gold = next(item for item in listings if "Lagoon" in item.title or "Lagoon" in item.description)
    scored = score_listing(gold)
    assert scored.tier == "🏆 GOLD"
    assert scored.has_ims_solution is True
    assert scored.color_match["name"] == "Lagoon Green Metallic"


def test_carsandbids_tiptronic_is_rejected():
    listings = CarsAndBidsScraper().parse(_load("carsandbids/search.json"))
    tip = next(item for item in listings if "Tiptronic" in item.title)
    scored = score_listing(tip)
    assert scored.tier == "REJECTED"


def test_carsandbids_extracts_structured_fields():
    listings = CarsAndBidsScraper().parse(_load("carsandbids/search.json"))
    first = listings[0]
    assert first.year == 2004
    assert first.mileage == 47500
    assert first.price == 22000
    assert first.price_is_auction is True
    assert first.location == "Austin, TX"
    assert first.vin == "WP0CB29874U660000"
    assert first.image_urls == ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]


# ---------- Classic.com ----------

def test_classic_dot_com_parses_three_cards():
    listings = ClassicDotComScraper().parse(_load("classic_dot_com/search.html"))
    assert len(listings) == 3


def test_classic_dot_com_extracts_year_mileage_price():
    listings = ClassicDotComScraper().parse(_load("classic_dot_com/search.html"))
    pine = next(item for item in listings if "Pine" in (item.color_exterior or ""))
    assert pine.year == 2004
    assert pine.mileage == 52300
    assert pine.price == 19500
    assert pine.location == "Portland, OR"


def test_classic_dot_com_pine_green_is_strong_or_gold():
    listings = ClassicDotComScraper().parse(_load("classic_dot_com/search.html"))
    pine = next(item for item in listings if "Pine" in (item.color_exterior or ""))
    scored = score_listing(pine)
    assert scored.score >= 70


def test_classic_dot_com_base_boxster_rejected():
    listings = ClassicDotComScraper().parse(_load("classic_dot_com/search.html"))
    base = next(item for item in listings if "2002" in item.title)
    scored = score_listing(base)
    assert scored.tier == "REJECTED"


# ---------- Craigslist ----------

def test_craigslist_parses_rss_feed():
    listings = CraigslistScraper().parse(_load("craigslist/philadelphia.rss"), city="philadelphia")
    assert len(listings) == 2


def test_craigslist_speed_yellow_scores_high():
    listings = CraigslistScraper().parse(_load("craigslist/philadelphia.rss"), city="philadelphia")
    yellow = next(item for item in listings if "Yellow" in item.title)
    scored = score_listing(yellow)
    assert scored.score >= 70
    assert scored.color_match["name"] == "Speed Yellow"


def test_craigslist_tiptronic_rejected():
    listings = CraigslistScraper().parse(_load("craigslist/philadelphia.rss"), city="philadelphia")
    tip = next(item for item in listings if "Tiptronic" in item.description)
    scored = score_listing(tip)
    assert scored.tier == "REJECTED"


def test_craigslist_attaches_city_as_location():
    listings = CraigslistScraper().parse(_load("craigslist/philadelphia.rss"), city="philadelphia")
    assert all(item.location == "philadelphia" for item in listings)
