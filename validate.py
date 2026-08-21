#!/usr/bin/env python3
"""Validate Hacker News scraper output.

Detects silent extraction failures: empty results, missing fields,
or wrong types. Exit code 0 = healthy, 1 = drift detected (trigger heal).
"""
import json
import sys

REQUIRED_FIELDS = {
    "title": str,
    "url": str,
    "points": int,
    "author": str,
    "comment_count": int,
}


def validate(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"FAIL: {path} not found")
        return False
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON — {e}")
        return False

    if not isinstance(data, list) or len(data) == 0:
        print("FAIL: no results returned (possible site layout change)")
        return False

    stories = data[0].get("stories", [])
    if not stories:
        print("FAIL: 'stories' array is empty — extraction silently failed")
        return False

    errors = []
    for i, story in enumerate(stories):
        for field, expected_type in REQUIRED_FIELDS.items():
            value = story.get(field)
            if value is None:
                # Job posts ("Is Hiring") legitimately have no author on HN
                if field == "author" and "hiring" in story.get("title", "").lower():
                    continue
                errors.append(f"story[{i}]: missing '{field}'")
            elif not isinstance(value, expected_type):
                # JSON numbers may arrive as float; accept ints only for counts
                errors.append(
                    f"story[{i}]: '{field}' is {type(value).__name__}, "
                    f"expected {expected_type.__name__}"
                )

    if errors:
        print(f"DRIFT DETECTED — {len(errors)} field issue(s):")
        for e in errors[:10]:
            print(f"  - {e}")
        return False

    print(f"OK: {len(stories)} stories, all required fields present and typed")
    return True


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "hn_result.json"
    sys.exit(0 if validate(path) else 1)
