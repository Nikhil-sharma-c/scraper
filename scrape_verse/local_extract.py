"""Local-mode Hacker News extractor — standard library only.

Produces records with EXACTLY the same schema as the Bright Data collector
({title, url, points, author, comment_count}) so the same validator, drift
detector, health score and doctor work identically on both modes.

Handles BOTH HN markups:
  classic: <a class="titlelink" href="URL">TITLE</a>
  modern : <span class="titleline"><a href="URL">TITLE</a>...</span>
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

HN_URL = "https://news.ycombinator.com"

_INT_RE = re.compile(r"-?\d+")


def _int(text: str | None) -> int | None:
    if not text:
        return None
    m = _INT_RE.search(text.replace("\xa0", " "))
    return int(m.group()) if m else None


class _HNParser(HTMLParser):
    """Parse news.ycombinator.com's table layout without deps."""

    def __init__(self):
        super().__init__()
        self.stories: list[dict] = []
        self._cur: dict | None = None
        self._capture: str | None = None   # which field we're capturing
        self._buf: list[str] = []
        self._await_title = False          # saw span.titleline, next <a> is the title

    # -- helpers ----------------------------------------------------------
    def _start_capture(self, field: str):
        self._capture = field
        self._buf = []

    def _end_capture(self):
        if self._capture and self._cur is not None:
            text = "".join(self._buf).strip()
            field = self._capture
            if field == "title":
                self._cur["title"] = text
            elif field == "url":
                self._cur["url"] = text
            elif field == "author":
                self._cur["author"] = text
            elif field == "points":
                self._cur["points"] = _int(text)
            elif field == "comment_count":
                self._cur["comment_count"] = _int(text)
        self._capture = None
        self._buf = []

    def _maybe_new_story(self):
        if self._cur is not None and (self._cur.get("title") or self._cur.get("url")):
            self.stories.append(self._cur)
        self._cur = {"title": "", "url": "", "points": None,
                     "author": "", "comment_count": None}

    # -- parser hooks ------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "tr" and "athing" in cls.split():
            self._maybe_new_story()
            return
        if self._cur is None:
            return
        # title container: next plain <a> is the story link
        if tag == "span" and "titleline" in cls.split():
            self._await_title = True
            return
        if tag != "a" and not (tag == "span" and "score" in cls.split()):
            return
        if tag == "a":
            if self._await_title or cls == "titlelink":
                self._start_capture("title")
                self._cur["url"] = a.get("href", "")
                self._await_title = False
            elif cls == "hnuser":
                self._start_capture("author")
            elif a.get("href", "").startswith("item?id=") \
                    and self._cur.get("comment_count") is None:
                self._start_capture("comment_count")
        else:  # <span class="score">
            self._start_capture("points")

    def handle_endtag(self, tag):
        if self._capture:
            if tag == "a" or (tag == "span" and self._capture in ("points",
                                                                  "comment_count")):
                self._end_capture()

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)


def fetch_html(url: str = HN_URL, timeout: int = 30) -> str:
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) scrape-verse-local/1.0",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract(html_text: str) -> list[dict]:
    parser = _HNParser()
    parser.feed(html_text)
    parser.close()
    parser._maybe_new_story()          # flush the final story
    stories = [s for s in parser.stories if s.get("title")]
    for s in stories:
        s.setdefault("points", None)
        s.setdefault("author", "")
        s.setdefault("comment_count", None)
    return stories


def extract_file(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return extract(f.read())


def run_local(url: str = HN_URL) -> dict:
    """Fetch + extract; returns a payload shaped like the collector output."""
    html_text = fetch_html(url)
    stories = extract(html_text)
    return [{"stories": stories, "product_page_url": url, "input": url}]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        stories = extract_file(sys.argv[1])
    else:
        payload = run_local()
        stories = payload[0]["stories"]
    print(json.dumps(stories[:3], indent=2))
    print(f"... total {len(stories)} stories")
