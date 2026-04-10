"""Parser tests for the Phase 2 scrapers (Cars & Bids + Classic.com).

These tests run against fixtures captured live from each source. The exact
listing content will rotate over time as old auctions end and new ones go up,
so the assertions focus on *structural* invariants:

  * the parser produces a non-empty (or correctly empty) list
  * each Listing has a valid URL, title, and source id
  * structured fields (year, price, mileage) are extracted when present
  * the scoring engine cleanly handles each listing without crashing

When fixtures are refreshed, run this file with -v to see which listings the
parser found and verify nothing's silently dropped.
"""

from pathlib import Path

import pytest

from boxster_hunter.models import Listing
from boxster_hunter.scoring import score_listing
from boxster_hunter.scrapers.carsandbids import CarsAndBidsScraper
from boxster_hunter.scrapers.classic_dot_com import ClassicDotComScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _load(rel: str) -> bytes:
    return (FIXTURES / rel).read_bytes()


# ---------- Cars & Bids ----------

@pytest.fixture
def cnb_listings():
    return CarsAndBidsScraper().parse(_load("carsandbids/rss.xml"))


def test_carsandbids_parses_only_boxster_titles(cnb_listings):
    # Cars & Bids RSS contains all current auctions; the scraper filters to
    # Boxster mentions before returning anything.
    assert all("boxster" in L.title.lower() for L in cnb_listings)


def test_carsandbids_listings_have_valid_urls(cnb_listings):
    for L in cnb_listings:
        assert isinstance(L, Listing)
        assert L.url_str.startswith("https://carsandbids.com/auctions/")
        assert L.source == "carsandbids"
        assert L.source_id  # short id from the URL path


def test_carsandbids_extracts_year_when_in_title(cnb_listings):
    for L in cnb_listings:
        if any(c.isdigit() for c in L.title):
            assert L.year is not None
            assert 1990 <= L.year <= 2030


def test_carsandbids_descriptions_are_text_not_html(cnb_listings):
    for L in cnb_listings:
        assert "<" not in L.description
        assert "&lt;" not in L.description


def test_carsandbids_scoring_runs_without_error(cnb_listings):
    for L in cnb_listings:
        scored = score_listing(L)
        assert scored.tier in {
            "🏆 GOLD",
            "🥇 STRONG",
            "🥈 REVIEW",
            "🥉 MARGINAL",
            "REJECTED",
        }


# ---------- Classic.com ----------

@pytest.fixture
def classic_listings():
    return ClassicDotComScraper().parse(_load("classic_dot_com/search.html"))


def test_classic_parses_listings_from_real_search_page(classic_listings):
    # The 986/s-manual/ search page reliably returns ~20+ listings.
    assert len(classic_listings) >= 5


def test_classic_listings_have_veh_urls(classic_listings):
    for L in classic_listings:
        assert L.url_str.startswith("https://www.classic.com/veh/")
        assert L.source == "classic.com"
        assert L.source_id.isdigit()


def test_classic_extracts_year_from_title(classic_listings):
    # Classic.com titles always lead with the year.
    for L in classic_listings:
        assert L.year is not None
        assert 1996 <= L.year <= 2005  # 986 generation bounds


def test_classic_extracts_mileage_when_present(classic_listings):
    with_mileage = [L for L in classic_listings if L.mileage is not None]
    assert len(with_mileage) >= 1
    for L in with_mileage:
        assert L.mileage > 0


def test_classic_extracts_price_when_present(classic_listings):
    with_price = [L for L in classic_listings if L.price is not None]
    assert len(with_price) >= 1
    for L in with_price:
        assert L.price > 0


def test_classic_dedupes_repeated_cards(classic_listings):
    """Each listing's card markup appears 2-3 times in the page (mobile/table
    layouts). The parser should dedupe by listing id."""
    ids = [L.source_id for L in classic_listings]
    assert len(ids) == len(set(ids))


def test_classic_titles_mention_boxster(classic_listings):
    for L in classic_listings:
        assert "boxster" in L.title.lower() or "porsche" in L.title.lower()
