# 🎬 Scrape-Verse — Demo Video Shooting Guide

**Goal:** a YouTube video, **max 3 minutes**, for the WeMakeDevs × Bright Data
hackathon submission form. Upload as **Unlisted**, paste the link in the form.

You do **NOT** need any Bright Data account or API key — every command below
runs fully offline.

---

## PART 1 — One-time setup (~15 min)

1. **Install Python** (if missing): https://www.python.org/downloads/
   → during install, tick **"Add Python to PATH"**.
   Check: open Command Prompt, type `python --version` → 3.11 or newer.
2. **Get the project:** download https://github.com/Nikhil-sharma-c/scraper
   (green **Code** button → **Download ZIP**) and unzip it, e.g. to `C:\scraper`.
3. **Copy the `data` folder** from this kit INTO the project folder
   (so the path is `C:\scraper\data\…`). Say **Yes** if Windows asks to merge/replace.
   This makes the GUI show the exact three site cards used in the narration.
4. **Start the app:** in Command Prompt:
   ```
   cd C:\scraper
   python -m scrape_verse.server
   ```
5. Open **http://127.0.0.1:8765** in Chrome/Edge.
   ✅ You should see **three cards**: *Hacker News 🟢*, *onlyflix.to 🟢*, *youtube.com 🟢*.
   Leave that tab open. Keep the server window running.
6. Open a **second** Command Prompt window (for Part 3 commands):
   ```
   cd C:\scraper
   ```

## PART 2 — Recording setup (~10 min)

7. Recorder: press **Win+G** (Xbox Game Bar, built into Windows) → start capture,
   or OBS if installed. Record at **1920×1080**.
8. Mic: any headset. Quiet room. Do a 20-second test recording — voice clear?
9. Browser zoom ~110–115%. Hide bookmarks bar (Ctrl+Shift+B). Close other tabs.

## PART 3 — The shoot (~25 min with retakes)

Speak slowly. After each command, pause one beat so viewers see the output.
Fluffed a line? Just say it again — mistakes get cut in editing.

---

### SHOT 1 — The control center (0:00–0:25) · *screen: browser*

**Show:** the three cards. Move the mouse across them.

**Say:**
> "This is Scrape-Verse — a web scraping control center where scrapers heal
> themselves. Every website I've scraped gets its own card with an honest
> health verdict. Three different sites, three different data schemas."

### SHOT 2 — Real data (0:25–0:55) · *screen: browser*

**Do:** click **View data** on the **onlyflix.to** card → table of movies opens
→ type "spider" in the filter box → click **Download JSON**.

**Say:**
> "I asked for movie name, rating, cast and release date in plain English —
> no code, no selectors. Bright Data's AI built the scraper, and here's the
> actual structured data: filterable, downloadable JSON."

### SHOT 3 — Silent failure (0:55–1:20) · *screen: terminal 2*

**Type:** `python sv.py demo hn_v2.html`  *(Enter)*

**Say:**
> "But scrapers break silently when sites redesign. This is a simulated
> Hacker News relayout — extraction didn't crash… it went quiet. Points
> dropped from 97 percent to zero. Our drift detector catches it, and the
> Scraper Doctor diagnoses exactly which selectors broke."

### SHOT 4 — Self-healing (1:20–1:45) · *screen: terminal 2*

**Type:** `python sv.py heal --mode "demo:hn_v2.html->hn_v3.html"`  *(Enter — include the quotes)*

**Say:**
> "Scrape-Verse sends a scoped repair back to Bright Data's healer, re-runs
> the collector, and verifies: health improved, drift cleared — the fix is
> accepted and versioned."

*(If output ends with ❌ REJECTED here, you typed the wrong fixture — use
hn_v3.html exactly as written above.)*

### SHOT 5 — Guardrails (1:45–2:05) · *screen: terminal 2*

**Type:** `python sv.py heal --mode "demo:hn_v2.html->hn_v4_badrepair.html"`

**Say:**
> "And if a repair makes things worse? Health collapses — the system rejects
> it and rolls back automatically. It never blindly trusts an AI."

### SHOT 6 — Audit trail & outro (2:05–2:30) · *screen: browser, refresh first*

**Do:** switch to the browser tab, refresh (F5), scroll to **Repair history**
and the **Activity** feed.

**Say:**
> "Every repair is versioned in an audit trail — that's why you can trust
> scraping that runs unattended. Scrape-Verse: ask in English, get structured
> data that survives redesigns. Clone it from the link below."

*(Exact percentages on screen may differ slightly from the narration — close enough is fine.)*

## PART 4 — Edit (~15 min)

10. Editor: **Clipchamp** (built into Windows 11) or CapCut (free).
11. Trim dead air between shots; cut retakes.
12. Add a **title card** at the start (text on dark background):
    `Scrape-Verse — web scraping that heals itself`
13. Add an **end card** (last 4 seconds):
    `github.com/Nikhil-sharma-c/scraper`

## PART 5 — Upload & hand-off (~10 min)

14. YouTube → upload → title:
    `Scrape-Verse — Self-Healing Web Scraper | WeMakeDevs x Bright Data Hackathon`
15. Visibility: **Unlisted**. Confirm duration is **≤ 3:00**.
16. Copy the link, open it in an **incognito window** to confirm it plays
    for strangers, then send the link to Nikhil for the submission form.
