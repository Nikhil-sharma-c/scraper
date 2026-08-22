#!/usr/bin/env python3
"""Build demo HTML snapshots used by `sv demo`.

v1 = healthy Hacker News front page
v2 = simulated redesign: score spans removed, author links stripped,
     points/comments gone -> triggers schema drift when replayed
v3 = partial recovery: scores back, authors still missing

Prefers the REAL live page (fetched once); falls back to a faithful
synthetic replica so the demo never depends on network or on HN's
current markup.
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo")
SNAP_V1 = os.path.join(DEMO, "hn_v1.html")


def fetch_real() -> str | None:
    try:
        sys.path.insert(0, ROOT)
        from scrape_verse.local_extract import fetch_html
        html_text = fetch_html()
        if "athing" in html_text:
            return html_text
    except Exception as exc:
        print(f"(live fetch unavailable: {exc}; using synthetic replica)")
    return None


SYNTHETIC_STORY = """
<tr class="athing submission" id="{id}">
  <td align="right" valign="top" class="title"><span class="rank">{rank}.</span></td>
  <td valign="top" class="title"><span class="titleline">
    <a href="{url}" class="titlelink">{title}</a>
    <span class="sitestr">({site})</span>
  </span></td>
</tr>
<tr><td></td><td class="subtext">
  <span class="subline">
    <span class="score" id="score_{id}">{points} points</span> by
    <a href="user?id={author}" class="hnuser">{author}</a>
    <span class="age" title="{ts}">{age} hours ago</span>
    | hide | past | web | favorite |
    <a href="item?id={id}">{comments}&nbsp;comments</a>
  </span>
</td></tr>
"""

STORIES = [
    ("Show HN: Scrape-Verse – a self-healing scraping agent", "https://github.com/example/scrape-verse", 645, "nikhil", 260),
    ("The day my CSS selectors quietly died", "https://example.dev/selectors-die", 512, "webwalker", 187),
    ("Bright Data launches AI Scraper Studio", "https://brightdata.com/blog/studio", 433, "datadiver", 95),
    ("SQLite is all you need for demos", "https://sqlite.org/whentouse.html", 388, "dbfan", 142),
    ("WeMakeDevs hackathon: Into the Scrape-Verse", "https://wemakedevs.org/scrapeverse", 301, "kunal", 74),
    ("A gentle introduction to schema drift", "https://example.org/schema-drift", 267, "pipewright", 58),
    ("Local LLMs are getting scary good at tools", "https://example.ai/local-tools", 240, "quantjock", 133),
    ("Why your scraper returns [] instead of errors", "https://example.net/silent-failures", 198, "silentfail", 41),
]


def build_synthetic() -> str:
    rows = []
    for i, (title, url, pts, author, comments) in enumerate(STORIES, start=1):
        site = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        rows.append(SYNTHETIC_STORY.format(
            id=4200000 + i * 7, rank=i, title=title, url=url, site=site,
            points=pts, author=author, comments=comments,
            ts="2026-08-22T12:00:00Z", age=(24 - i * 2)))
    return ("<html><body><table><tr><td></td><td>News</td></tr>"
            + "".join(rows) + "</table></body></html>")


def strip_scores(html_text: str) -> str:
    """v2 redesign: remove score spans + comment counts + author links."""
    text = re.sub(r'<span class="score"[^>]*>.*?</span>', "", html_text)
    text = re.sub(r'<a href="user\?id=[^"]*" class="hnuser">[^<]*</a>', "", text)
    text = re.sub(r'<a href="item\?id=\d+">\d+(&nbsp;|\s)*comments?</a>', "", text)
    return text


def strip_authors_only(html_text: str) -> str:
    """Partial recovery variant: scores back, authors still gone."""
    return re.sub(r'<a href="user\?id=[^"]*" class="hnuser">[^<]*</a>', "", html_text)


def bad_repair(html_text: str) -> str:
    """v4: a 'repair' that made things WORSE — titles/links break too."""
    text = strip_scores(html_text)
    text = text.replace('class="titleline"', 'class="titleline-v9"')   # renamed container
    text = re.sub(r'<a href="[^"]*" class="titlelink">', "<span>", text)  # classic markup gone
    return text


def main():
    os.makedirs(DEMO, exist_ok=True)
    v1 = fetch_real() or build_synthetic()
    source = "real news.ycombinator.com" if "athing" in v1 else "synthetic replica"
    with open(SNAP_V1, "w", encoding="utf-8") as f:
        f.write(v1)
    with open(os.path.join(DEMO, "hn_v2.html"), "w", encoding="utf-8") as f:
        f.write(strip_scores(v1))
    with open(os.path.join(DEMO, "hn_v3.html"), "w", encoding="utf-8") as f:
        f.write(strip_authors_only(v1))
    with open(os.path.join(DEMO, "hn_v4_badrepair.html"), "w", encoding="utf-8") as f:
        f.write(bad_repair(v1))
    print(f"Wrote demo/hn_v1.html ({source}), hn_v2.html (drifted), "
          f"hn_v3.html (partial recovery), hn_v4_badrepair.html (worse)")


if __name__ == "__main__":
    main()
