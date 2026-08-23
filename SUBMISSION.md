# Submission kit — Into the Scrape-Verse (closes Aug 23)

Everything below is copy-paste ready. Fill the two `<placeholders>`, record the
video, submit.

---

## 1. Project description (submission form)

Scrape-Verse is a self-healing web scraping control center built on Bright Data
Scraper Studio. Paste any public URL plus a plain-language request ("scrape all
movie name, rating, cast and release date") and Scraper Studio's AI builds and
hosts a collector for that site; Scrape-Verse wraps every run in a closed loop:
validate → compare with previous runs → diagnose → heal → re-run → verify.

Because scrapers fail *silently* when sites redesign, a schema-drift detector
flags field drops (e.g. points 97%→0%), a "Scraper Doctor" produces an
evidence-based diagnosis with confidence, and a scoped repair prompt goes to
`bdata scraper heal`. A repair is only accepted if the post-heal health score
improves AND drift clears — otherwise it is rejected and rolled back, with
every version kept in an audit trail.

Everything lands in a human-friendly GUI: one health card per website with
plain-language status, per-field quality bars, drift findings, repair history,
and a data browser (filter, copy, download JSON). Three different sites were
scraped live during development — Hacker News (100%), an Onlyflix movie catalog
(92%), and a YouTube channel (100%) — each judged by its own inferred schema.

## 2. "How was Scraper Studio used?" (form field)

- **Create:** targets are described in plain English through the Bright Data
  CLI; Scraper Studio's AI generated and hosts each collector — Hacker News
  (`c_mt39p31p2mji0agjy0`) plus two more built the same way during development:
  an Onlyflix movie catalog and a YouTube channel (title/thumbnail/views).
- **Run:** jobs are dispatched from our local server (`bdata scraper run`),
  asynchronously, with live progress in the GUI while Studio builds.
- **Heal (the core):** when extraction drifts, our doctor generates a scoped
  repair prompt naming broken vs working fields and calls
  `bdata scraper heal --auto-approve --auto-save`. Verified live against the
  pinned HN collector: heal completed, post-heal re-run returned 100% schema
  validity, recorded as v3 in the healing history.
- **Verify & own output:** every run returns structured JSON scored by a
  five-component health score (schema validity, field completeness, record
  count, URL validity, historical consistency); the structured records power
  the GUI's data browser and dashboard. Generated scraper code is ours;
  healing never changes collector IDs, so nothing downstream breaks.

## 3. Demo video script (≤3 min, GUI-first)

Pre-flight (off-camera): `python -m scrape_verse.server` running at
http://127.0.0.1:8765 with the three cards visible; font size up; `bdata`
authenticated.

| # | On screen | Say |
|---|---|---|
| 1 | GUI: three green/yellow cards (HN, onlyflix.to, youtube.com) | "This is Scrape-Verse — a self-healing scraping control center on Bright Data. Each site I've scraped gets its own card with an honest health verdict." |
| 2 | Click onlyflix **View data** → table of movies | "I asked in plain English for movie name, rating, cast, release date. Studio's AI built the collector; here are the real records — browsable, filterable, downloadable." |
| 3 | Terminal: break a fixture (`python sv.py demo hn_v2.html`) → doctor report | "But scrapers die silently when sites redesign. Points dropped 97→0%. The doctor catches it and diagnoses selector drift with evidence." |
| 4 | Terminal: `python sv.py heal --mode 'demo:hn_v2.html->hn_v3.html'` | "A scoped repair goes back to Bright Data's healer. Re-run, verify: health up, drift cleared — accepted as v2." |
| 5 | Same command with bad fixture v4 | "And if the AI makes it *worse*? Health tanks — repair rejected, rolled back automatically." |
| 6 | GUI: Repair history panel + activity feed | "Every repair is versioned. This audit trail is why you can trust unattended scraping." |

End frame: repo URL + tagline "Same collector ID. Nothing downstream ever breaks."

## 4. Pre-submit checklist

- [ ] Push repo to GitHub (public), update `<you>` in README quickstart
- [ ] Record video per script above; upload (YouTube unlisted or Loom)
- [ ] Registration form (if not done): https://www.wemakedevs.org/hackathons/scrape-verse → Register
- [ ] Submission form: repo + video + §1 text + §2 text
- [ ] LinkedIn post tagging WeMakeDevs (Daily Bugle track — free watch raffle entry)
- [ ] Masked keys check: no tokens in repo or video (`git log -p | grep -i token`)
