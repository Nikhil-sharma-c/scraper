#!/usr/bin/env bash
# Self-healing scraper loop for the Scrape-Verse hackathon.
#
# 1. Run the Bright Data collector
# 2. Validate the output schema
# 3. If validation fails, ask the AI to heal the scraper and re-run
#
# Usage: bash heal.sh
set -euo pipefail

COLLECTOR_ID="c_mt39p31p2mji0agjy0"
URL="https://news.ycombinator.com"
RESULT_FILE="hn_result.json"
MAX_HEAL_ATTEMPTS=2

echo "=== [1/3] Running collector $COLLECTOR_ID ==="
if ! bdata scraper run "$COLLECTOR_ID" "$URL" --json -o "$RESULT_FILE" >/dev/null 2>&1; then
    echo "Run failed — will attempt heal"
fi

echo "=== [2/3] Validating output ==="
attempt=0
until python validate.py "$RESULT_FILE"; do
    attempt=$((attempt + 1))
    if [ "$attempt" -gt "$MAX_HEAL_ATTEMPTS" ]; then
        echo "Healing failed after $MAX_HEAL_ATTEMPTS attempts — manual review needed"
        exit 1
    fi

    echo "=== [3/3] Healing (attempt $attempt/$MAX_HEAL_ATTEMPTS) ==="
    bdata scraper heal "$COLLECTOR_ID" \
        "The Hacker News front page output is missing or has invalid fields (title, url, points, author, comment_count). Re-inspect https://news.ycombinator.com and repair the extraction so every story returns all five fields with correct types." \
        --approve

    echo "Re-running collector after heal..."
    bdata scraper run "$COLLECTOR_ID" "$URL" --json -o "$RESULT_FILE" >/dev/null 2>&1 || true
done

echo "=== Done: data is healthy ==="
