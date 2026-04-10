"""Classic.com scraper. Server-rendered HTML, parsed with BeautifulSoup."""

from __future__ import annotations

from bs4 import BeautifulSoup

from boxster_hunter.models import Listing
from boxster_hunter.scrapers.base import BaseScraper

SEARCH_URL = "https://www.classic.com/m/porsche/boxster/986/s-manual/"


class ClassicDotComScraper(BaseScraper):
    source = "classic.com"

    def fetch_listings(self) -> list[Listing]:
        resp = self.http_get(SEARCH_URL)
        resp.raise_for_status()
        return self.parse(resp.text)

    def parse(self, payload: str | bytes) -> list[Listing]:
        soup = BeautifulSoup(payload, "lxml")
        listings: list[Listing] = []
        for card in soup.select("article.vehicle-card, div.vehicle-card"):
            link = card.select_one("a.vehicle-card__link, a[href]")
            if not link or not link.get("href"):
                continue
            href = link["href"]
            url = href if href.startswith("http") else f"https://www.classic.com{href}"
            title = _text(card.select_one(".vehicle-card__title, h3, h2"))
            year = _first_year(title)
            mileage = _to_int(_text(card.select_one(".vehicle-card__mileage, .mileage")))
            price = _price_to_int(_text(card.select_one(".vehicle-card__price, .price")))
            location = _text(card.select_one(".vehicle-card__location, .location"))
            description = _text(card.select_one(".vehicle-card__description, .description"))
            color = _text(card.select_one(".vehicle-card__color, .color"))
            source_id = href.rstrip("/").rsplit("/", 1)[-1]
            listings.append(
                Listing(
                    source=self.source,
                    source_id=source_id,
                    url=url,
                    first_seen=self.now(),
                    last_updated=self.now(),
                    title=title,
                    description=description,
                    year=year,
                    mileage=mileage,
                    price=price,
                    location=location,
                    color_exterior=color or None,
                )
            )
        return listings


def _text(node) -> str:
    if node is None:
        return ""
    return node.get_text(strip=True)


def _first_year(text: str) -> int | None:
    import re

    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def _to_int(text: str) -> int | None:
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else None


def _price_to_int(text: str) -> int | None:
    return _to_int(text)
