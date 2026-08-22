#!/usr/bin/env python3
"""Trigger the pinned Bright Data collector via its production DCA endpoint.

Demonstrates that the c_* Collector ID is a live API — no deployment step:

    python trigger_api.py                 # pretty-printed JSON to stdout
    python trigger_api.py -o out.json     # also save raw payload
    BASE_URL=... API_TOKEN=... python trigger_api.py

Falls back to the CLI (`bdata scraper run`) when no API token is configured,
so the demo always works.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

COLLECTOR_ID = "c_mt39p31p2mji0agjy0"
TARGET_URL = "https://news.ycombinator.com"

DEFAULT_BASE = "https://api.brightdata.com"
TOKEN_ENV_KEYS = ("API_TOKEN", "BRIGHTDATA_API_TOKEN", "BD_API_TOKEN")


def get_token() -> str | None:
    for key in TOKEN_ENV_KEYS:
        token = os.environ.get(key, "").strip()
        if token:
            return token
    return None


def trigger_via_api(token: str, base_url: str, timeout: int = 300) -> object:
    """POST /dca/trigger — the collector-as-API production path."""
    from urllib.request import Request, urlopen

    endpoint = f"{base_url}/dca/trigger?collector={COLLECTOR_ID}"
    body = json.dumps([{"url": TARGET_URL}]).encode()
    req = Request(endpoint, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser(description="Trigger collector via DCA API")
    ap.add_argument("-o", "--output", default=None, help="also write raw JSON here")
    args = ap.parse_args()

    token = get_token()
    if token:
        print(f"Triggering {COLLECTOR_ID} via POST /dca/trigger ...")
        try:
            payload = trigger_via_api(token, os.environ.get("BASE_URL", DEFAULT_BASE))
        except Exception as exc:
            print(f"API trigger failed ({exc.__class__.__name__}: {exc}); "
                  f"falling back to CLI.")
            payload = None
    else:
        payload = None
        print("No API token in env (API_TOKEN/BRIGHTDATA_API_TOKEN); using CLI fallback.")

    if payload is None:
        import subprocess, shutil
        bdata = next((shutil.which(n) for n in ("bdata", "bdata.cmd") if shutil.which(n)), None)
        if not bdata:
            sys.exit("bdata CLI not found and no API token configured")
        proc = subprocess.run(
            [bdata, "scraper", "run", COLLECTOR_ID, TARGET_URL, "--json"],
            capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            sys.exit(f"CLI run failed: {proc.stderr or proc.stdout}")
        payload = json.loads(proc.stdout)

    stories = payload[0].get("stories", []) if isinstance(payload, list) and payload else []
    print(f"OK: {len(stories)} stories extracted from {TARGET_URL}")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved: {args.output}")
    else:
        print(json.dumps(payload[:1], indent=2)[:800] + ("..." if len(json.dumps(payload)) > 800 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
