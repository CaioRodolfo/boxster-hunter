"""Parser tests for the four forum/auction scrapers (PCARMARKET + 3 forums).

Like test_scrapers_easy, these run against live-captured fixtures and assert
structural invariants rather than specific listing content (which rotates).
"""

from pathlib import Path

import pytest

from boxster_hunter.models import Listing
from boxster_hunter.scoring import score_listing as _score_listing
from boxster_hunter.scrapers.audiworld import AudiWorldScraper
from boxster_hunter.scrapers.boxster_forum import BoxsterForumScraper
from boxster_hunter.scrapers.pcarmarket import PCarMarketScraper
from boxster_hunter.scrapers.planet9 import Planet9Scraper
from boxster_hunter.scrapers.rennlist import RennlistScraper
from boxster_hunter.scrapers.yotatech import YotaTechScraper
from boxster_hunter.targets import PORSCHE_986_BOXSTER_S

FIXTURES = Path(__file__).parent / "fixtures"


def score_listing(listing):
    return _score_listing(listing, PORSCHE_986_BOXSTER_S)


def _load(rel: str) -> bytes:
    return (FIXTURES / rel).read_bytes()


# ---------- PCARMARKET ----------

@pytest.fixture
def pcm_listings():
    return PCarMarketScraper().parse(_load("pcarmarket/api.json"))


def test_pcarmarket_filters_to_boxsters_only(pcm_listings):
    # The api.json fixture contains 10 active Porsches; the parser keeps
    # only Boxsters. The fixture may legitimately have zero Boxsters at
    # capture time — that's still valid behavior.
    for L in pcm_listings:
        assert "boxster" in L.title.lower()


def test_pcarmarket_listings_have_required_fields(pcm_listings):
    for L in pcm_listings:
        assert L.source == "pcarmarket"
        assert L.url_str.startswith("https://www.pcarmarket.com/auction/")
        assert L.title
        assert L.price_is_auction is True


# ---------- 986forum ----------

@pytest.fixture
def b986_listings():
    return BoxsterForumScraper().parse(_load("boxster_forum/forsale.html"))


def test_986forum_finds_threads(b986_listings):
    assert len(b986_listings) >= 1


def test_986forum_listings_well_formed(b986_listings):
    for L in b986_listings:
        assert L.source == "986forum"
        assert L.url_str.startswith("https://986forum.com/forums/")
        assert L.source_id.isdigit()
        assert L.title


def test_986forum_scoring_runs_without_error(b986_listings):
    for L in b986_listings:
        scored = score_listing(L)
        assert scored.tier in {
            "🏆 GOLD", "🥇 STRONG", "🥈 REVIEW", "🥉 MARGINAL", "REJECTED",
        }


# ---------- Rennlist ----------

@pytest.fixture
def rennlist_listings():
    return RennlistScraper().parse(_load("rennlist/forsale.html"))


def test_rennlist_finds_threads(rennlist_listings):
    # The for-sale subforum is high-volume; we should always pick up many.
    assert len(rennlist_listings) >= 5


def test_rennlist_listings_well_formed(rennlist_listings):
    for L in rennlist_listings:
        assert L.source == "rennlist"
        assert L.url_str.startswith("https://rennlist.com/forums/")
        assert L.source_id.isdigit()
        assert isinstance(L, Listing)


def test_rennlist_scoring_runs_without_error(rennlist_listings):
    for L in rennlist_listings:
        score_listing(L)


# ---------- Planet-9 ----------

@pytest.fixture
def planet9_listings():
    return Planet9Scraper().parse(_load("planet9/forsale.html"))


def test_planet9_finds_threads(planet9_listings):
    assert len(planet9_listings) >= 1


def test_planet9_unique_thread_ids(planet9_listings):
    """Each XenForo thread appears once per cell in the page; we dedupe by tid."""
    ids = [L.source_id for L in planet9_listings]
    assert len(ids) == len(set(ids))


def test_planet9_skips_label_anchors(planet9_listings):
    """Make sure we picked the title anchor, not the 'Sticky'/'Sold' badge."""
    for L in planet9_listings:
        assert L.title.lower() not in {"sticky", "sold", "want to buy"}


def test_planet9_listings_well_formed(planet9_listings):
    for L in planet9_listings:
        assert L.source == "planet9"
        assert L.url_str.startswith("https://www.planet-9.com/threads/")
        assert L.source_id.isdigit()


# ---------- AudiWorld ----------

@pytest.fixture
def audiworld_listings():
    return AudiWorldScraper().parse(_load("audiworld/marketplace.html"))


def test_audiworld_finds_threads(audiworld_listings):
    # The marketplace landing page usually has 25-30 active threads.
    assert len(audiworld_listings) >= 5


def test_audiworld_listings_well_formed(audiworld_listings):
    for L in audiworld_listings:
        assert L.source == "audiworld"
        assert L.url_str.startswith("https://www.audiworld.com/forums/")
        assert L.source_id.isdigit()
        assert L.title


def test_audiworld_uses_vbulletin_thread_id_pattern(audiworld_listings):
    # Reuses the parse_vbulletin helper, so source_id should be the numeric
    # thread id from id="thread_title_{N}".
    ids = [L.source_id for L in audiworld_listings]
    assert all(i.isdigit() for i in ids)
    assert len(ids) == len(set(ids))


# ---------- YotaTech ----------

@pytest.fixture
def yotatech_listings():
    return YotaTechScraper().parse(_load("yotatech/marketplace.html"))


def test_yotatech_finds_threads(yotatech_listings):
    # f108 (Vehicles - Trailers Complete) typically has 100+ threads.
    assert len(yotatech_listings) >= 10


def test_yotatech_listings_well_formed(yotatech_listings):
    for L in yotatech_listings:
        assert L.source == "yotatech"
        assert L.url_str.startswith("https://www.yotatech.com/forums/")
        assert L.source_id.isdigit()
        assert L.title


def test_yotatech_subforum_has_4runner_listings(yotatech_listings):
    """The classifieds carry all Toyota vehicles — confirm at least some
    4Runner mentions exist so we know the source is feeding the right target."""
    has_4runner = any("4runner" in L.title.lower() for L in yotatech_listings)
    assert has_4runner
