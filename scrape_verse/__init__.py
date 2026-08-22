"""Scrape-Verse: self-healing scraping agent (cloud Bright Data + local mode)."""
import os
import sys

__version__ = "0.2.0"

# Windows consoles/pipes may default to cp1252; our CLI prints emoji markers.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)
