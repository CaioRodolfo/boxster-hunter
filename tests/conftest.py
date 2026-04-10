"""Shared fixtures for the test suite."""

from datetime import UTC, datetime

import pytest

from boxster_hunter.models import Listing


def make_listing(
    *,
    source: str = "test",
    source_id: str = "abc123",
    url: str = "https://example.com/listing/abc123",
    title: str = "2004 Porsche Boxster S",
    description: str = "",
    year: int | None = 2004,
    mileage: int | None = 65000,
    price: int | None = 18500,
    **overrides,
) -> Listing:
    base = {
        "source": source,
        "source_id": source_id,
        "url": url,
        "first_seen": datetime.now(UTC),
        "last_updated": datetime.now(UTC),
        "title": title,
        "description": description,
        "year": year,
        "mileage": mileage,
        "price": price,
    }
    base.update(overrides)
    return Listing(**base)


@pytest.fixture
def make_listing_fixture():
    return make_listing
