"""Notion sink tests. Verifies the property payload + dry-run path."""

import responses

from boxster_hunter.notion_sink import NotionSink
from boxster_hunter.scoring import score_listing as _score_listing
from boxster_hunter.targets import PORSCHE_986_BOXSTER_S
from tests.conftest import make_listing


def score_listing(listing):
    return _score_listing(listing, PORSCHE_986_BOXSTER_S)


def build_properties(listing):
    """Test helper — calls the Boxster target's property builder directly."""
    return PORSCHE_986_BOXSTER_S.build_notion_properties(listing)


def _scored_gold():
    return score_listing(
        make_listing(
            title="2004 Porsche Boxster S — Lagoon Green Metallic",
            description="6-speed manual, IMS Solution installed. Service records.",
            mileage=47500,
            price=22000,
            location="Austin, TX",
        )
    )


def test_build_properties_includes_required_fields():
    listing = _scored_gold()
    props = build_properties(listing)

    assert props["Tier"]["select"]["name"] == "🏆 GOLD"
    assert props["Score"]["number"] == listing.score
    assert props["Year"]["number"] == 2004
    assert props["Mileage"]["number"] == 47500
    assert props["Price"]["number"] == 22000
    assert props["IMS Status"]["select"]["name"] == "Solution"
    assert props["Color"]["select"]["name"] == "Green"
    assert props["URL"]["url"].startswith("https://")
    assert "Lagoon Green" in props["Title"]["title"][0]["text"]["content"] or "Green" in props["Title"]["title"][0]["text"]["content"]
    assert props["Location"]["rich_text"][0]["text"]["content"] == "Austin, TX"
    assert props["Transmission"]["select"]["name"] == "6-speed manual"


def test_build_properties_normalizes_low_miles_flag():
    listing = _scored_gold()
    props = build_properties(listing)
    flag_names = {f["name"] for f in props["Flags"]["multi_select"]}
    assert "📉 Low miles" in flag_names
    assert all("(" not in name for name in flag_names if name.startswith("📉"))


def test_build_properties_unknown_ims_when_no_signal():
    listing = score_listing(
        make_listing(
            title="2004 Porsche Boxster S 3.2L",
            description="6-speed manual, just had a tune-up.",
        )
    )
    props = build_properties(listing)
    assert props["IMS Status"]["select"]["name"] == "Unknown"


def test_dry_run_when_no_credentials(monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    sink = NotionSink(target=PORSCHE_986_BOXSTER_S)
    assert sink.dry_run is True
    page_id = sink.create_listing_page(_scored_gold())
    assert page_id.startswith("dry-run-")


@responses.activate
def test_create_listing_page_posts_to_notion_when_credentialed():
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/pages",
        json={"id": "fake-page-id-12345"},
        status=200,
    )
    sink = NotionSink(target=PORSCHE_986_BOXSTER_S, api_key="secret_test", database_id="db123")
    page_id = sink.create_listing_page(_scored_gold())
    assert page_id == "fake-page-id-12345"
    sent = responses.calls[0].request
    assert sent.headers["Authorization"] == "Bearer secret_test"
    body = sent.body.decode()
    assert "Green" in body
    assert "GOLD" in body
