# 986 Boxster S Hunter

Automated listing aggregator and scoring engine for finding the right 2003–2004
Porsche Boxster S (3.2L, 6-speed manual, IMS bearing addressed, target colors).
Scrapes a half-dozen sources, scores each listing 0–100 against the target spec,
deduplicates against a local SQLite database, and routes high-quality matches to
a Notion database with tiered email/Slack notifications.

## Layout

```
boxster_hunter/
  models.py       Pydantic v2 Listing model
  colors.py       Target color codes + matching
  scoring.py      Scoring engine (0-100, tier assignment)
  db.py           SQLite dedup layer
  notion_sink.py  Notion API client
  notifier.py     Email + Slack dispatch
  main.py         Orchestrator
  scrapers/
    base.py       BaseScraper ABC
    carsandbids.py
    classic_dot_com.py
    craigslist.py
    pcarmarket.py
    boxster_forum.py
    rennlist.py
    planet9.py
tests/
  fixtures/       Saved HTML/JSON for parser tests
```

## Quickstart

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

To run the hunter (dry-run, no env vars required):

```bash
uv run python -m boxster_hunter.main --dry-run
```

To run live:

```bash
cp .env.example .env
# Fill in NOTION_API_KEY, NOTION_DATABASE_ID, etc.
uv run python -m boxster_hunter.main
```

## Configuration

All integrations are env-var gated. If a credential is missing, that sink
silently no-ops and logs what it *would* have sent. The hunter still runs end
to end against scraping + scoring + SQLite, so you can develop and test the
core pipeline without any third-party accounts.

| Env var | Required | Purpose |
| --- | --- | --- |
| `NOTION_API_KEY` | live runs | Notion integration token |
| `NOTION_DATABASE_ID` | live runs | Target database for listings |
| `SLACK_WEBHOOK_URL` | optional | Incoming webhook for STRONG+ alerts |
| `SENDGRID_API_KEY` | optional | Email alerts for STRONG+ |
| `ALERT_EMAIL` | optional | Recipient for email alerts |
| `BOXSTER_DB_PATH` | optional | SQLite path (default `boxster.db`) |

## Defaults / open questions resolved

The spec's Section 16 open questions are resolved as follows. Override any of
these by editing the relevant module:

- **Persistent SQLite**: local file at `boxster.db`. For GitHub Actions, the
  workflow uses `actions/cache` with the run number as the key — the file is
  best-effort only. Move to Turso (or commit-back) when this becomes painful.
- **Rate limiting**: 1 request/second per source via `BaseScraper`. Tune in
  `boxster_hunter/scrapers/base.py`.
- **User-agent rotation**: enabled by default; rotates through a small pool of
  desktop browser UAs in `BaseScraper`.
- **Geographic filter**: not a hard reject. Listings far from Wilmington, DE
  still flow through scoring; consider filtering in Notion views.
- **Price ceiling**: not a hard reject. Listings over $25K still flow through;
  use the score for filtering.

## Development

```bash
uv sync --extra dev
uv run pytest -v
uv run ruff check .
uv run ruff format .
```

Tests are pure unit tests against committed fixtures — no live HTTP. To capture
fresh fixtures from a real source, save the response body under
`tests/fixtures/<source>/<name>.{html,json}` and add a parser test for it.

## Architecture

See the spec page in Notion for the full architecture diagram and rationale.
The high-level flow:

```
scrapers → parser → SQLite dedup → scoring → tier dispatch
                                                 ├─ Notion (always for ≥REVIEW)
                                                 ├─ Email  (STRONG+)
                                                 ├─ Slack  (STRONG+)
                                                 └─ SMS    (GOLD only, optional)
```
