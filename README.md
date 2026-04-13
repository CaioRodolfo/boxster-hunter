# Car Hunter

Automated multi-target car listing aggregator. One cron, many cars.

Each "target" is a Python config file under `boxster_hunter/targets/` that
fully describes one car-shaped thing the system hunts for: which scrapers it
consumes, which year range counts, the disqualifier patterns, the positive
scoring rules, the color map, the Notion database to write into, and the
Slack channel to ping. The scoring engine is generic — it applies whatever
rules a target gives it. Adding a third car is "write a new target file."

## Active targets

| Target | What we hunt for | Notion DB env var | Slack env var |
| --- | --- | --- | --- |
| `porsche_986_boxster_s` | 2003-2004 Boxster S, 6-speed manual, IMS-addressed, target color | `NOTION_DATABASE_ID` | `SLACK_WEBHOOK_URL` |
| `audi_s3_8v_facelift` | 2017-2020 Audi S3 (8V facelift), Premium Plus / Prestige, B&O sound, documented Haldex maintenance, "cool" color | `NOTION_DATABASE_ID_S3` | `SLACK_WEBHOOK_URL_S3` |

## Sources

| Source | Strategy | Notes |
| --- | --- | --- |
| Bring a Trailer | Site-wide WordPress RSS at `/feed/` | Rich descriptions. `robots.txt` allows `/feed/`. |
| Cars & Bids | RSS feed at `/rss.xml` | All makes; orchestrator routes to whichever target's title keyword matches. |
| Classic.com | Phoenix LiveView HTML scraping | Price-tracker, not seller listings — no body text. GH Actions IPs sometimes 403. |
| PCARMARKET | JSON API at `/api/auctions/?make=porsche` | Porsche-only. |
| 986forum | vBulletin `a[id^="thread_title_"]` + post-body enrichment | Porsche 986 only. |
| Rennlist | vBulletin (same as 986forum) + enrichment | Porsche general for-sale forum. |
| Planet-9 | XenForo `h3.structItem-title` + `div.bbWrapper` enrichment | Porsche only. |
| AudiWorld | JSON-LD `Car` schema embedded in `.shelf-item` divs | Audi-specific. Their marketplace publishes structured data per listing. |

**Excluded** — Cloudflare-gated, would need a residential proxy or headless browser:
* Craigslist (RSS 403'd from cloud IPs, HTML fallback empty without JS)
* AudiZine (full Cloudflare challenge on every URL, plus explicit anti-AI robots.txt)
* AutoTrader, Cars.com, CarGurus, CarMax (all behind aggressive bot detection)

eBay Motors has a real public API and would be a clean add — deferred for now.

## Layout

```
boxster_hunter/
  models.py             Pydantic v2 Listing model
  scoring.py            Generic scoring engine (knows nothing about specific cars)
  db.py                 SQLite dedup layer
  notion_sink.py        Generic Notion API client (target-aware)
  notifier.py           Generic Slack/email/SMS dispatch (target-aware)
  main.py               Orchestrator — fetch once, score per target, dispatch per target
  sources.py            Source display name map
  targets/
    base.py             TargetConfig dataclass + match_color helper
    porsche_986_boxster_s.py
    audi_s3_8v_facelift.py
  scrapers/
    base.py             BaseScraper ABC + default enrich_description
    _rss_common.py      Shared helpers for Cars & Bids + BaT
    _forum_common.py    Shared helpers for vBulletin + XenForo
    carsandbids.py
    bringatrailer.py
    classic_dot_com.py
    pcarmarket.py
    boxster_forum.py
    rennlist.py
    planet9.py
    audiworld.py
    craigslist.py       Stub — see module docstring
tests/
  fixtures/             Saved HTML/JSON for parser tests
```

## Quickstart

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Dry run (no env vars required):

```bash
uv run python -m boxster_hunter.main --dry-run
```

Live run:

```bash
cp .env.example .env
# Fill in NOTION_API_KEY plus the per-target *_DATABASE_ID and *_WEBHOOK_URL vars
uv run python -m boxster_hunter.main
```

## Configuration

All integrations are env-var gated. Missing creds → log-only no-op so the
pipeline still runs end to end. Per-target env var names live on the
`TargetConfig` instance for each target — the orchestrator looks them up at
runtime, so you never have to edit Python to add a new car's secrets.

| Env var | Required by | Purpose |
| --- | --- | --- |
| `NOTION_API_KEY` | live runs | Single Notion integration token (shared across targets) |
| `NOTION_DATABASE_ID` | Boxster | "986 Hunt" database id `ee4dfdd8471d4d9e9c0bfa7144f11bd1` |
| `NOTION_DATABASE_ID_S3` | S3 | "8V S3 Hunt" database id `90ab1bf07cd142cf98408b01e6a98139` |
| `SLACK_WEBHOOK_URL` | optional | Slack channel for Boxster STRONG+ alerts |
| `SLACK_WEBHOOK_URL_S3` | optional | Slack channel for S3 STRONG+ alerts |
| `SENDGRID_API_KEY` + `ALERT_EMAIL` | optional | Cross-target email alerts |
| `TWILIO_*` | optional | Cross-target SMS alerts |
| `BOXSTER_DB_PATH` | optional | SQLite dedup path (default `boxster.db`) |

## Adding a new target

1. Write `boxster_hunter/targets/{your_car}.py` defining `TARGET = TargetConfig(...)`.
2. Add it to `ALL_TARGETS` in `boxster_hunter/targets/__init__.py`.
3. Create a Notion database for the target (any schema you want; the target's
   `build_notion_properties` function controls the column mapping).
4. Add a Slack webhook env var name on the target and set the secret.
5. Run the suite — no engine changes needed.

## Known limitations

* **Search-index scoring is shallow.** Some scrapers (Classic.com, vBulletin
  forums on the listing index) only return titles. The orchestrator runs a
  detail-fetch enrichment pass for those, but Cloudflare/IP blocks on detail
  pages can prevent enrichment from succeeding.
* **GitHub Actions IPs are sometimes blocked** by Cloudflare on Classic.com.
  The orchestrator's exit code tolerates per-source failures so the cron
  doesn't spam you with failure notifications.

## Schedule

Cron runs hourly from 8am-8pm Eastern. See `.github/workflows/hunt.yml`.
GitHub cron is UTC-only and does not observe DST — when EDT → EST in
November, swap the cron expression as documented in the workflow file.
