# Into the Scrape-Verse — Self-Healing Hacker News Scraper

WeMakeDevs × Bright Data hackathon entry (Aug 17–23, 2026).

## What this is

A **self-healing web scraper** built on [Bright Data Scraper Studio](https://brightdata.com),
driven entirely from the terminal via the `bdata` CLI inside an AI coding agent (Hermes Agent).

The core idea: instead of hand-writing CSS selectors that break when a site redesigns,
we describe the data we want in plain language. Bright Data's AI generates and hosts the
scraper (a "Collector"). When the target site changes its layout, the scraper is repaired
with a single prompt (`bdata scraper heal`) — same Collector ID, same output shape,
nothing downstream breaks.

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  scheduler   │ --> │ bdata scraper run    │ --> │ hn_result.json│
│  (cron/GH Act)│    │ c_mt37n2r5qje96fkb7  │     │ (raw data)    │
└─────────────┘     └──────────┬───────────┘     └──────┬───────┘
                               │ on failure / schema drift │
                               ▼                        ▼
                    ┌──────────────────────┐     ┌──────────────┐
                    │ bdata scraper heal    │     │ validate.py   │
                    │ (AI repairs selector) │     │ (schema check)│
                    └──────────────────────┘     └──────────────┘
```

- **Collector ID:** `c_mt39p31p2mji0agjy0` ([view in dashboard](https://brightdata.com/cp/scrapers/c_mt39p31p2mji0agjy0))
- **Target:** Hacker News front page
- **Output shape:** `{stories: [{title, url, points, author, comment_count}], product_page_url, input}`

## Files

| File | Purpose |
|------|---------|
| `validate.py` | Schema validation — detects silent extraction failures |
| `heal.sh` | One-command self-heal loop: run → validate → heal → re-run |
| `hn_result.json` | Latest scrape output |

## Usage

```bash
# Run the scraper
bdata scraper run c_mt37n2r5qje96fkb7 "https://news.ycombinator.com" --json -o hn_result.json

# Validate the output
python validate.py hn_result.json

# Full self-healing loop
bash heal.sh
```

## Why self-healing matters

Traditional scrapers die quietly:

```
.product-grid > .card .price   →   site redesign   →   returns []
```

Nobody notices until the dashboard is empty for a week. This project closes that loop:
validation detects the drift, healing rewrites the extraction against the original
plain-language description, and the data keeps flowing.
