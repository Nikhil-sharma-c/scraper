# Submission kit — Into the Scrape-Verse (closes Aug 23)

Everything below is copy-paste ready. Fill the two `<placeholders>`, record the
video, submit.

---

## 1. Project description (submission form, ~180 words)

Scrape-Verse is a self-healing web scraping agent built on Bright Data Scraper
Studio and driven entirely from the terminal through a coding agent. A plain-
language prompt created Collector `c_mt39p31p2mji0agjy0`, which extracts the
Hacker News front page into clean JSON. Because scrapers fail *silently* when
sites redesign, every run is wrapped in a closed loop: validate → compare with
previous runs → diagnose → heal → re-run → verify. A schema-drift detector
flags field drops (e.g. points 97%→0%), an AI "Scraper Doctor" produces an
evidence-based diagnosis with a confidence score, and a scoped repair prompt
is sent to `bdata scraper heal`. After healing, the pipeline re-runs and
scores a five-component health score: a repair is only accepted if health
improves AND drift clears — otherwise it is rejected and rolled back
automatically. Every repair is versioned into an audit trail. A dependency-free
local extractor mirrors the collector's exact schema for offline demos, and a
static dashboard visualizes runs, drift events, repairs, and healing stats.
The structured output feeds a generated ops dashboard — data in, product out.

## 2. "How was Scraper Studio used?" (form field)

- **Create:** described the target in plain English via the Bright Data CLI;
  Scraper Studio's AI generated and hosts the collector
  (`c_mt39p31p2mji0agjy0`), returning structured JSON
  `{stories:[{title,url,points,author,comment_count}]}`.
- **Run:** triggered from our `sv.py` agent CLI (`bdata scraper run`) and via
  the production endpoint path (`POST /dca/trigger`, see `trigger_api.py`).
- **Heal (the core of the project):** when extraction drifts, our doctor
  generates a scoped repair prompt naming broken vs working fields and calls
  `bdata scraper heal --auto-approve --auto-save`. Verified live during
  development: heal completed, post-heal cloud re-run returned 100% schema
  validity, recorded as v3 in the healing history.
- **Ownership:** the generated scraper code is ours; healing never changes the
  collector ID or downstream consumers.

## 3. Demo video script (~90 sec, terminal only)

Pre-flight (off-camera): `python tools/build_snapshots.py` once; fresh
`rm -rf data` so history starts clean; font size up.

| # | On screen | Say |
|---|---|---|
| 1 | `python sv.py health` → 🟢 100% | "This scraper watches Hacker News through a Bright Data AI collector. Today it's perfectly healthy." |
| 2 | `python sv.py demo hn_v2.html` → ⚠️ banner + doctor report | "But sites redesign. Here's a simulated HN relayout — watch: extraction didn't error, it went silent. Points dropped 97 to zero percent. Our drift detector catches it, and the Scraper Doctor diagnoses selector drift with evidence and 98% confidence." |
| 3 | `python sv.py heal --mode 'demo:hn_v2.html->hn_v3.html'` | "The doctor writes a scoped repair prompt — fix ONLY the broken selectors. The collector heals, we re-run, and verification compares health: 84 to 92 percent, drift cleared — repair accepted, recorded as version 2." |
| 4 | `python sv.py heal --mode 'demo:hn_v2.html->hn_v4_badrepair.html'` | "And if the AI makes it worse? Health drops to 8 — repair REJECTED, rolled back automatically. The system doesn't blindly trust the model." |
| 5 | `python sv.py history` then `python sv.py dashboard` | "Every repair is versioned — including a real heal we ran against the live Bright Data collector. This dashboard is what the structured JSON powers: an ops view of scraper reliability." |

Recording notes:
- Quote the `'demo:a->b'` strings (the `>` eats shells otherwise).
- Show `bdata` at least once on camera (criterion: Use of Scraper Studio) —
  step 1 can open with a real `bdata scraper run c_mt39p31p2mji0agjy0 ...`
  if you want the live-cloud flex; budget impact $0.
- End frame: repo URL + "same Collector ID. Nothing downstream ever breaks."

## 4. Pre-submit checklist

- [ ] Push repo to GitHub (public), update `<you>` in README quickstart
- [ ] Record video per script above; upload (YouTube unlisted or Loom)
- [ ] Registration form (if not done): https://www.wemakedevs.org/hackathons/scrape-verse → Register
- [ ] Submission form: repo + video + §1 text + §2 text
- [ ] LinkedIn post tagging WeMakeDevs (Daily Bugle track — free watch raffle entry)
- [ ] Masked keys check: no tokens in repo or video (`git log -p | grep -i token`)
