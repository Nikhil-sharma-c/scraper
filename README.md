# Into the Scrape-Verse — Self-Healing Web Scraping Agent

WeMakeDevs × Bright Data hackathon entry (Aug 17–23, 2026).

## What this is

A **model-agnostic, self-healing web scraping agent**. Describe the data you want in
plain language; a Bright Data AI Collector extracts it in the cloud. When the target
site redesigns, extraction fails *silently* — so Scrape-Verse wraps every run in a
closed loop:

```
run → validate → compare with previous runs → diagnose → heal
    → re-run → verify → accept ✅ / reject + rollback ❌
```

Two execution modes, one schema:

| Mode | Engine | Use case |
|------|--------|----------|
| ☁️ Cloud | Bright Data Scraper Studio Collector | production reliability |
| 💻 Local | stdlib Python extractor (`scrape_verse/local_extract.py`) | privacy, cost, offline |

Both produce identical records (`title, url, points, author, comment_count`), so the
validator, drift detector, health score, doctor and healing history work unchanged.

- **Collector ID:** `c_mt39p31p2mji0agjy0`
  ([dashboard](https://brightdata.com/cp/scrapers/c_mt39p31p2mji0agjy0))
- **Target:** Hacker News front page · 30 stories · 5 fields

## Features

1. **Schema-drift detector** — profiles field completeness per run and diffs against
   the previous run. `points: 97% → 0% (CRITICAL)` fires automatically; no human
   staring at dashboards.
2. **Scraper Health Score** — five weighted components (schema validity, field
   completeness, record count, URL validity, historical consistency) rolled into
   🟢 HEALTHY ≥85 / 🟡 DEGRADED ≥60 / 🔴 BROKEN <60.
3. **AI Scraper Doctor** — turns raw failures into an evidence-based diagnosis with
   confidence % and a scoped repair prompt ("fix ONLY these selectors, don't disturb
   the working fields").
4. **Healing version history** — every accepted/rejected repair is recorded:
   `v3 · reason · health_before → health_after · prompt`.
5. **Automatic verification + rollback** — a repair is only kept if health actually
   improves and drift clears; otherwise it's rejected and rolled back.

## Quickstart

Zero dependencies beyond **Python 3.10+** (stdlib only — nothing to pip install).

```bash
git clone https://github.com/Nikhil-sharma-c/scraper.git
cd scraper
python -m scrape_verse.server                 # control center → http://127.0.0.1:8765
npm i -g @brightdata/cli && bdata login       # one-time Bright Data OAuth
```

Paste any public URL plus a plain-language request ("get product name and price
from every listing") and hit **Start scraping** — the first run teaches Bright
Data's AI the site (5–25 min), then each site gets its own health card and
re-runs take seconds. Prefer the terminal?

```bash
python sv.py run --mode cloud                 # run pinned Collector c_mt39p31p2mji0agjy0
python sv.py heal --mode auto                 # closed-loop healing against the live site
```

## GUI / desktop control center

Prefer a graphical workflow? Start the local GUI:

```bash
python -m scrape_verse.server
# open http://127.0.0.1:8765
```

### GUI workflow

Paste any public URL plus a plain-language query ("get product name and price
from every listing") and each site gets its own health card with **View data**
(filterable table, copy/download JSON) and **↻ Re-run** actions, plain-language
status, a live progress stepper while jobs run, an activity feed, and the
repair history.

A native Electron shell is also included:

```bash
cd desktop
npm install
npm start
# package a portable Windows build:
npm run dist
```

The Electron app starts the same Python API server and opens the GUI in a
native desktop window. No credentials are stored by the GUI; Bright Data
authentication remains in the normal CLI credential store.

## Full CLI tour

```bash
# 1. Run + validate + score (auto: cloud collector, falls back to local extractor)
python sv.py run

# 2. Health dashboard in your terminal
python sv.py health
python sv.py compare          # field-by-field diff of recent runs

# 3. Diagnose like a doctor
python sv.py doctor

# 4. Full closed-loop healing (detect → diagnose → heal → re-run → verify)
python sv.py heal --mode auto

# 5. Version history of repairs
python sv.py history
python sv.py events           # event log

# 6. Static HTML dashboard
python sv.py dashboard                 # → dashboard.html
```

Legacy entry points still work: `python validate.py hn_result.json`, `bash heal.sh`.

## Architecture

```
                ┌──────────────────────────────────────────┐
                │               sv.py (CLI)                │
                └───────┬─────────────────────┬────────────┘
                        │                     │
              ┌─────────▼────────┐   ┌────────▼─────────┐
              │  CLOUD MODE      │   │  LOCAL MODE       │
              │  bdata scraper   │   │  stdlib HTML      │
              │  run/heal        │   │  extractor        │
              └─────────┬────────┘   └────────┬─────────┘
                        └────────┬────────────┘
                                 ▼
                    identical JSON schema
                                 ▼
             ┌──────────────────────────────────────┐
             │ core.py: profile → compare → health  │
             │ doctor: diagnosis + scoped prompt    │
             │ healer: heal → re-run → verify       │
             │         accept ✅ / reject+rollback  │
             └──────────────────┬───────────────────┘
                                ▼
            data/runs.json · versions.json · events.json
                                ▼
                  terminal output + dashboard.html
```

## Files

| Path | Purpose |
|------|---------|
| `sv.py` | CLI: run/health/doctor/compare/heal/history/events/dashboard |
| `scrape_verse/core.py` | profiling, drift detection, health score, doctor, version/event stores |
| `scrape_verse/local_extract.py` | dependency-free HN extractor (dual-markup) |
| `scrape_verse/healer.py` | closed-loop orchestration + accept/reject verification |
| `scrape_verse/dashboard.py` | static dark-theme HTML dashboard generator |
| `demo/hn_v1..v4*.html` | healing-test HTML fixtures (offline repair-loop testing) |
| `validate.py`, `heal.sh` | original hackathon entry points (still functional) |
| `data/*.json` | run history, healing versions, event log |

## Why self-healing matters

Traditional scrapers die quietly:

```
.product-grid > .card .price   →   site redesign   →   returns []
```

Nobody notices until the dashboard is empty for a week. Scrape-Verse closes that loop:
drift is detected within one run cycle, the diagnosis is specific enough to act on,
the repair is verified against a health baseline, and a bad repair can never silently
replace a good scraper.
