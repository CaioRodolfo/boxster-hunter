"""PCARMARKET auction scraper."""

from __future__ import annotations

from boxster_hunter.models import Listing
from boxster_hunter.scrapers._forum_common import CardSelectors, parse_cards
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.pcarmarket.com/auction/category/porsche/boxster/"

SELECTORS = CardSelectors(
    card="div.auction-card, article.auction-card",
    link="a.auction-card__link, a[href]",
    title=".auction-card__title, h3",
    price=".auction-card__price, .price",
    mileage=".auction-card__mileage, .mileage",
    location=".auction-card__location, .location",
    description=".auction-card__description, .description",
    base_url="https://www.pcarmarket.com",
)


class PCarMarketScraper(BaseScraper):
    source = "pcarmarket"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        return parse_cards(payload, SELECTORS, self.source, self.now)
