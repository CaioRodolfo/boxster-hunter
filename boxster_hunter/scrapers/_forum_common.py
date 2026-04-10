"""Shared helpers for forum/auction-card style scrapers.

PCARMARKET, 986forum, Rennlist, and Planet-9 all return a list of cards or
thread rows that we extract with BeautifulSoup. The shape is similar enough
that a small parameterized helper covers all four.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from boxster_hunter.models import Listing


@dataclass
class CardSelectors:
    """CSS selectors for one source's listing cards."""

    card: str
    link: str  # selector for the <a href> inside a card
    title: str | None = None  # if None, title is the link text
    price: str | None = None
    mileage: str | None = None
    location: str | None = None
    description: str | None = None
    base_url: str = ""  # prepended to relative hrefs


def parse_cards(
    payload: str | bytes,
    selectors: CardSelectors,
    source: str,
    now,
) -> list[Listing]:
    soup = BeautifulSoup(payload, "lxml")
    out: list[Listing] = []
    for card in soup.select(selectors.card):
        link = card.select_one(selectors.link)
        if link is None or not link.get("href"):
            continue
        href = link["href"]
        url = href if href.startswith("http") else f"{selectors.base_url}{href}"
        title = _select_text(card, selectors.title) or link.get_text(strip=True)
        description = _select_text(card, selectors.description)
        price = _to_int(_select_text(card, selectors.price))
        mileage = _to_int(_select_text(card, selectors.mileage))
        location = _select_text(card, selectors.location) or None
        out.append(
            Listing(
                source=source,
                source_id=_source_id_from_url(url),
                url=url,
                first_seen=now(),
                last_updated=now(),
                title=title,
                description=description,
                year=_first_year(title) or _first_year(description),
                price=price,
                mileage=mileage,
                location=location,
            )
        )
    return out


def _select_text(card: Tag, selector: str | None) -> str:
    if not selector:
        return ""
    node = card.select_one(selector)
    if node is None:
        return ""
    return node.get_text(" ", strip=True)


def _first_year(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else None


def _to_int(text: str) -> int | None:
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    return int(digits) if digits else None


def _source_id_from_url(url: str) -> str:
    last = url.rstrip("/").rsplit("/", 1)[-1]
    return last.split("?")[0].split(".")[0] or url
