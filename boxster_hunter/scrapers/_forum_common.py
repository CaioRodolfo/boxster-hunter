"""Shared parsers and enrichment helpers for forum-style scrapers.

Two forum engines power the four forum sources:

  * **vBulletin 3.x** (986forum, Rennlist) — each thread is rendered as a
    table row with an anchor `<a id="thread_title_{tid}">`. The href is the
    canonical thread URL.
  * **XenForo 2.x** (Planet-9) — each thread is a `<div class="structItem">`
    containing `<div class="structItem-title"><a href="/threads/{slug}.{tid}/">`.

Both fixtures don't expose price or mileage on the listing index — those live
inside the individual thread bodies. We surface the title only and let the
scoring engine extract intent (year, IMS mentions, color hints).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from boxster_hunter.models import Listing

_TID_RE = re.compile(r"thread_title_(\d+)")


def parse_vbulletin(payload: str | bytes, source: str, base_url: str, now) -> list[Listing]:
    soup = BeautifulSoup(payload, "lxml")
    out: list[Listing] = []
    seen_tids: set[str] = set()
    # Sticky threads get rendered twice per page (once in the "Sticky" section,
    # once in the normal list) and the two anchors can carry slightly different
    # hrefs (trailing slash, session params). Dedup by thread id so downstream
    # code never sees the same listing twice — this matches parse_xenforo.
    for anchor in soup.find_all("a", id=_TID_RE):
        tid_match = _TID_RE.match(anchor.get("id", ""))
        if not tid_match:
            continue
        tid = tid_match.group(1)
        if tid in seen_tids:
            continue
        href = anchor.get("href", "")
        if not href:
            continue
        seen_tids.add(tid)
        url = href if href.startswith("http") else f"{base_url}{href}"
        title = anchor.get_text(" ", strip=True)
        out.append(
            Listing(
                source=source,
                source_id=tid,
                url=url,
                first_seen=now(),
                last_updated=now(),
                title=title,
                description=title,
                year=_first_year(title),
            )
        )
    return out


def parse_xenforo(payload: str | bytes, source: str, base_url: str, now) -> list[Listing]:
    soup = BeautifulSoup(payload, "lxml")
    out: list[Listing] = []
    seen_tids: set[str] = set()
    for title_node in soup.find_all(class_="structItem-title"):
        anchor = _first_thread_link(title_node)
        if anchor is None:
            continue
        href = anchor.get("href", "")
        if not href or "/threads/" not in href:
            continue
        url = href if href.startswith("http") else f"{base_url}{href}"
        tid = _xenforo_tid(href)
        if tid in seen_tids:
            continue
        seen_tids.add(tid)
        title = anchor.get_text(" ", strip=True)
        out.append(
            Listing(
                source=source,
                source_id=tid,
                url=url,
                first_seen=now(),
                last_updated=now(),
                title=title,
                description=title,
                year=_first_year(title),
            )
        )
    return out


def _first_thread_link(title_node: Tag) -> Tag | None:
    """Pick the title anchor inside a XenForo h3.structItem-title.

    Each h3 contains a leading badge anchor (Sticky/Sold/Want to Buy) and the
    real title anchor. The title anchor is always the *last* /threads/ link in
    the node — the badge comes first.
    """
    candidates = [
        a for a in title_node.find_all("a")
        if "/threads/" in a.get("href", "") and not a.get("href", "").endswith("/latest")
    ]
    return candidates[-1] if candidates else None


def _xenforo_tid(href: str) -> str:
    """XenForo URLs end in `.{tid}/`."""
    parts = href.rstrip("/").rsplit(".", 1)
    if len(parts) == 2:
        return parts[1].split("/")[0]
    return href.rstrip("/").rsplit("/", 1)[-1]


def _first_year(text: str) -> int | None:
    """Best-effort year extraction from a listing title.

    Forum titles are messy. Sellers write any of:

      * "2008 Toyota 4Runner" — clean 4-digit year (preferred form)
      * "19854runner $12000" — 4-digit year mashed against the model name
      * "85 4runner" — 2-digit year at title start
      * "'90 4runner" — 2-digit year with leading apostrophe
      * "90' 4runner" — 2-digit year with trailing apostrophe
      * "99 Limited 4runner|Tucson, AZ" — 2-digit at start, model later

    We try those forms in order; the first hit wins. If nothing matches,
    return None and let downstream filters do their best without a year.
    """
    if not text:
        return None
    # 1) Clean 4-digit year somewhere in the text
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        return int(m.group(0))
    # 2) 4-digit year mashed against the next char without whitespace
    # (e.g. "19854runner" → 1985). The (19|20)\d{2} prefix prevents bare
    # 4-digit numbers like "12000" from matching.
    m = re.search(r"(19|20)\d{2}", text)
    if m:
        return int(m.group(0))
    # 3) 2-digit year at start of title (with optional surrounding apostrophes)
    m = re.match(r"['\s]*(\d{2})['\s]", text.strip())
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy < 30 else 1900 + yy
    return None


def extract_first_post_body(html: str | bytes, selector: str) -> str | None:
    """Return the text of the first post body matching the given selector.

    Used by enrich_description() overrides to skip page chrome (nav, footer,
    sidebars, "vBulletin Solutions" footer text) and only score against the
    actual seller pitch. Returns None if no body is found.
    """
    soup = BeautifulSoup(html, "lxml")
    nodes = soup.select(selector)
    if not nodes:
        return None
    text = nodes[0].get_text(" ", strip=True)
    return text or None
