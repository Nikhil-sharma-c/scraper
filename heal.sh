#!/usr/bin/env bash
# Self-healing scraper loop for the Scrape-Verse hackathon (legacy entry point).
#
# The full engine now lives in `sv.py`. This script keeps the original
# one-command experience and delegates to it.
#
# Usage: bash heal.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Scrape-Verse self-healing loop (via sv CLI) ==="
python sv.py heal --mode auto --target hackernews
