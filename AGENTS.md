# AGENTS.md — Scrape-Verse agent rules

Pin for every coding agent (Claude Code, Cursor, Codex, Hermes) working in this repo.

## Pinned Collector

- **Collector ID:** `c_mt39p31p2mji0agjy0` (Hacker News front page)
- **Dashboard:** https://brightdata.com/cp/scrapers/c_mt39p31p2mji0agjy0
- Do NOT rebuild this scraper per session — reuse the pinned ID via the CLI.

## Command cheat sheet

```bash
# Run the pinned collector (real cloud extraction)
bdata scraper run c_mt39p31p2mji0agjy0 "https://news.ycombinator.com" --json -o hackernews_result.json

# Validate + score + record the run (never skip)
python sv.py run --mode cloud

# Diagnose / repair when validation fails
python sv.py doctor
python sv.py heal --mode auto          # full loop: diagnose -> heal -> re-run -> verify
```

## Project conventions

- Entry point is `sv.py`; engine lives in `scrape_verse/` (core/healer/local_extract/dashboard).
- Every run must go through `healer.evaluate()` so run history, drift detection,
  health score and the event log stay consistent. Don't hand-roll validation.
- Repairs are accepted ONLY if post-heal health improves and drift clears;
  otherwise rejected + rolled back (`data/versions.json` audit trail).
- Demo/offline work uses snapshot replay: `python sv.py demo hn_v2.html`.
  Quote mode strings containing `->` in shells.
- Public data only; never commit tokens or `.env`.
