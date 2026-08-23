"""Scrape-Verse core engine.

Schema profiling, run history, schema-drift detection, scraper health score,
Scraper-Doctor diagnosis, healing version history with auto-rollback support,
and an event log. Pure standard library — runs anywhere Python 3 runs.

Data layout (all under <repo>/data):
    runs.json        list of RunRecord dicts (newest last)
    versions.json    per-collector healing version history
    events.json      append-only event log for the dashboard
"""
from __future__ import annotations

import json
import os
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

TARGETS = {
    "hackernews": {
        "label": "Hacker News",
        "url": "https://news.ycombinator.com",
        "collector": "c_mt39p31p2mji0agjy0",
        "stories_path": [0, "stories"],
        "expected_records": 30,
    },
}

REQUIRED_FIELDS = ["title", "url", "points", "author", "comment_count"]
FIELD_TYPES = {"title": str, "url": str, "points": int, "author": str, "comment_count": int}
DRIFT_THRESHOLD = 0.10   # a field dropping more than this share triggers drift
COUNT_TOLERANCE = 0.25   # record count may vary 25% before flagging

# --------------------------------------------------------------------------
# dynamic targets (registered at runtime via GUI/API jobs)
# --------------------------------------------------------------------------

DYNAMIC_TARGETS_FILE = os.path.join(DATA_DIR, "targets.json")


def load_dynamic_targets() -> dict:
    return _read_json(DYNAMIC_TARGETS_FILE, {})


def get_target(key: str) -> dict:
    """Unified target lookup: built-in or dynamically registered."""
    raw = TARGETS.get(key) or load_dynamic_targets().get(key) or {}
    t = dict(raw)
    t.setdefault("key", key)
    t.setdefault("label", key.replace("_", " ").title())
    t.setdefault("url", "")
    t.setdefault("collector", "")
    t.setdefault("stories_path", [0, "stories"])
    t.setdefault("expected_records", 30)
    return t


def register_target(key: str, label: str, url: str, collector_id: str = "",
                    expected_records: int | None = None, query: str = "",
                    **extra) -> dict:
    dyn = load_dynamic_targets()
    entry = {
        "label": label or key,
        "url": url,
        "collector": collector_id,
        "expected_records": expected_records or 30,
        "query": query,
        "registered_at": utcnow(),
    }
    entry.update(extra)                     # backend, api_url, api_header, …
    dyn[key] = entry
    _write_json(DYNAMIC_TARGETS_FILE, dyn)
    return entry


TARGET_STATE_FILE = os.path.join(DATA_DIR, "target_state.json")


def set_target_state(key: str, **fields) -> None:
    """Track lifecycle state (building/running/ready/error/no_data) per target."""
    states = _read_json(TARGET_STATE_FILE, {})
    st = states.setdefault(key, {})
    st.update(fields)
    st["updated_at"] = utcnow()
    _write_json(TARGET_STATE_FILE, states)


def get_target_state(key: str) -> dict:
    return _read_json(TARGET_STATE_FILE, {}).get(key, {})


def all_target_keys() -> list[str]:
    return list(TARGETS.keys()) + [k for k in load_dynamic_targets()
                                   if k not in TARGETS]


# --------------------------------------------------------------------------
# small utils
# --------------------------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return deepcopy(default)
    except json.JSONDecodeError:
        return deepcopy(default)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _get_nested(obj, path):
    """Walk e.g. [0, 'stories'] through nested lists/dicts."""
    for key in path:
        try:
            obj = obj[key]
        except (IndexError, KeyError, TypeError):
            return []
    return obj if isinstance(obj, list) else []


# --------------------------------------------------------------------------
# schema profiling
# --------------------------------------------------------------------------

def extract_records(raw: object, target: str = "hackernews") -> list:
    """Pull the record list out of an arbitrary collector payload shape."""
    stories_path = get_target(target)["stories_path"]
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "stories" in raw[0]:
        return _get_nested(raw, stories_path)
    if isinstance(raw, dict) and "stories" in raw:
        return raw["stories"] or []
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]      # flat record list
    if isinstance(raw, dict):
        for key in ("results", "data", "items", "rows", "records",
                    "movies", "products", "posts", "listings"):
            v = raw.get(key)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        for v in raw.values():                              # first dict-list anywhere
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def is_url_ok(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _observed_fields(records: list) -> list[str]:
    """Union of record keys, order-stable (arbitrary-site schemas).

    Keys whose values are always containers (dict/list — e.g. Bright Data's
    echoed `input` job params) are metadata, not data fields, and are skipped.
    """
    names: list[str] = []
    scalar_seen: dict[str, bool] = {}
    for rec in records:
        if isinstance(rec, dict):
            for k, v in rec.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, (str, int, float, bool)) or v is None:
                    scalar_seen[k] = True
                scalar_seen.setdefault(k, False)
                if k not in names:
                    names.append(k)
    return [k for k in names if scalar_seen.get(k)][:12]


def profile(records: list) -> dict:
    """Compute per-field completeness stats over a list of records."""
    observed = _observed_fields(records)
    # Use the HN schema only when records genuinely look like HN stories
    # (most of its fields present) — two coincidental overlaps like
    # title+author must NOT force HN judging onto foreign payloads.
    hn_overlap = len(set(REQUIRED_FIELDS) & set(observed))
    if hn_overlap >= 3:
        names = REQUIRED_FIELDS            # HN-schema family: judge all five
    else:
        names = observed                   # arbitrary site: judge its own fields
    fields = {}
    for name in names:
        total = valid = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            total += 1
            value = rec.get(name)
            expected = FIELD_TYPES.get(name)
            if expected is not None:
                ok = isinstance(value, expected) and not (isinstance(value, str) and not value.strip())
            else:                          # unknown field: any non-empty scalar
                ok = isinstance(value, (str, int, float, bool)) and \
                     not (isinstance(value, str) and not value.strip())
            # job posts legitimately lack an author on HN
            if name == "author" and ("hiring" in str(rec.get("title", "")).lower()
                                     and (value is None or value == "")):
                ok = True
            if name == "points" and isinstance(value, float) and value.is_integer():
                ok = True
            if name == "comment_count" and isinstance(value, float) and value.is_integer():
                ok = True
            if name == "url" and ok and not is_url_ok(value):
                ok = False
            valid += 1 if ok else 0
        pct = round(100.0 * valid / total, 2) if total else 0.0
        fields[name] = {"valid": valid, "total": total, "pct": pct}
    # url validity: find links wherever they live (url, product_page_url,
    # thumbnail, …) instead of assuming an HN-shaped schema. If the query
    # asked for no link-like fields at all, this component is None/N-A.
    any_urls = False
    urls_ok = 0
    for rec in records:
        if not isinstance(rec, dict):
            continue
        links = [v for v in rec.values()
                 if isinstance(v, str) and v.strip().lower().startswith(("http://", "https://"))]
        if not links:
            continue
        any_urls = True
        if all(is_url_ok(link) for link in links):
            urls_ok += 1
    return {
        "n_records": len(records),
        "fields": fields,
        "url_valid_pct": (round(100.0 * urls_ok / len(records), 2)
                          if records and any_urls else None),
        "sample": deepcopy(records[:3]),
    }


# --------------------------------------------------------------------------
# run history
# --------------------------------------------------------------------------

RUNS_FILE = os.path.join(DATA_DIR, "runs.json")
VERSIONS_FILE = os.path.join(DATA_DIR, "versions.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")


def save_run(result_path: str, source: str = "unknown", mode: str = "cloud",
             target: str = "hackernews", note: str = "") -> dict:
    """Profile a result file and append it to the run history."""
    raw = _read_json(result_path, None)
    if raw is None:
        raise FileNotFoundError(f"result file not found or invalid JSON: {result_path}")
    records = extract_records(raw, target)
    prof = profile(records)
    runs = _read_json(RUNS_FILE, [])
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run = {
        "id": f"{ts}.{time.time_ns() % 1_000_000:06d}-{mode}",
        "timestamp": utcnow(),
        "target": target,
        "source": source,
        "mode": mode,
        "result_file": result_path,
        "note": note,
        "profile": prof,
    }
    runs.append(run)
    _write_json(RUNS_FILE, runs[-500:])
    log_event("run", f"Run recorded: {target} via {mode} — "
                     f"{prof['n_records']} records, completeness {_completeness(prof):.0f}%",
              target=target, mode=mode, run_id=run["id"])
    return run


def get_history(target: str | None = None, limit: int = 50) -> list:
    runs = _read_json(RUNS_FILE, [])
    if target:
        runs = [r for r in runs if r.get("target") == target]
    return runs[-limit:]


def load_run(run_id: str) -> dict | None:
    for run in _read_json(RUNS_FILE, []):
        if run["id"] == run_id:
            return run
    return None


def previous_run(current_run: dict) -> dict | None:
    """The most recent earlier run for the same target."""
    runs = [r for r in get_history(current_run.get("target"))
            if r["id"] != current_run["id"] and r["timestamp"] <= current_run["timestamp"]]
    return runs[-1] if runs else None


def _completeness(prof: dict) -> float:
    fields = prof.get("fields", {})
    if not fields:
        return 0.0
    return sum(f["pct"] for f in fields.values()) / len(fields)


# --------------------------------------------------------------------------
# schema-drift detection
# --------------------------------------------------------------------------

def compare(prev_prof: dict, cur_prof: dict, threshold: float = DRIFT_THRESHOLD,
            count_tolerance: float = COUNT_TOLERANCE) -> list:
    """Compare two schema profiles; return a list of drift findings."""
    findings = []
    prev_fields = prev_prof.get("fields", {})
    cur_fields = cur_prof.get("fields", {})

    for name in sorted(set(prev_fields) | set(cur_fields)):
        p = prev_fields.get(name, {}).get("pct", 100.0)
        c = cur_fields.get(name, {}).get("pct", 0.0)
        if c - p <= -(threshold * 100):
            severity = "critical" if p >= 90 and c <= 30 else "warning"
            findings.append({
                "kind": "field_drop",
                "severity": severity,
                "field": name,
                "prev_pct": p,
                "new_pct": c,
                "delta": round(c - p, 2),
            })

    p_n = prev_prof.get("n_records", 0)
    c_n = cur_prof.get("n_records", 0)
    if p_n and (c_n < p_n * (1 - count_tolerance)):
        findings.append({
            "kind": "record_count_drop",
            "severity": "warning",
            "field": "_records",
            "prev_pct": 100.0,
            "new_pct": round(100.0 * c_n / p_n, 2),
            "delta": round(c_n - p_n, 2),
            "detail": f"records {p_n} -> {c_n}",
        })
    elif p_n == 0 and c_n == 0:
        findings.append({
            "kind": "empty_result",
            "severity": "critical",
            "field": "_records",
            "prev_pct": None,
            "new_pct": 0.0,
            "delta": 0.0,
            "detail": "no records extracted in either run",
        })
    return findings


# --------------------------------------------------------------------------
# health score
# --------------------------------------------------------------------------

WEIGHTS = {
    "schema_validity": 0.20,
    "field_completeness": 0.20,
    "record_count": 0.20,
    "url_validity": 0.20,
    "historical_consistency": 0.20,
}


def health_score(run: dict, prev: dict | None = None) -> dict:
    prof = run.get("profile", run)  # accept either a run record or bare profile
    fields = prof.get("fields", {})

    if fields:
        perfect = sum(f.get("total", 0) for f in fields.values())
        got = sum(f.get("valid", 0) for f in fields.values())
        schema_validity = round(100.0 * got / perfect, 2) if perfect else 0.0
    else:
        schema_validity = 0.0

    field_completeness = round(_completeness(prof), 2)

    trec = get_target(run.get("target", "hackernews")).get(
        "expected_records",
        TARGETS.get(run.get("target"), TARGETS["hackernews"]).get("expected_records", 30))
    n = prof.get("n_records", 0)
    if n == 0:
        record_count = 0.0
    elif prof.get("fields"):
        record_count = 100.0          # arbitrary sites: no baseline to judge count
    else:
        record_count = round(min(100.0, 100.0 * n / trec), 2)

    # None = target legitimately has no link-like fields → N-A, not zero.
    url_validity = prof.get("url_valid_pct")
    if url_validity is None:
        url_validity = None
    else:
        url_validity = float(url_validity)

    if prev is None:
        consistency = 100.0
    else:
        drops = []
        pf = prev.get("profile", prev).get("fields", {})
        for name, f in fields.items():
            p_pct = pf.get(name, {}).get("pct", 100.0)
            drop = p_pct - f.get("pct", 0.0)
            drops.append(max(0.0, drop))
        consistency = round(max(0.0, 100.0 - (sum(drops) / len(drops) if drops else 0)), 2)

    components = {
        "schema_validity": schema_validity,
        "field_completeness": field_completeness,
        "record_count": record_count,
        "url_validity": url_validity,          # may be None → excluded
        "historical_consistency": consistency,
    }
    active = {k: v for k, v in components.items() if v is not None}
    wsum = sum(WEIGHTS[k] for k in active)
    overall = round(sum(components[k] * WEIGHTS[k] for k in active) / wsum, 1) \
        if wsum else 0.0
    status, emoji = ("HEALTHY", "🟢") if overall >= 85 else \
                    ("DEGRADED", "🟡") if overall >= 60 else \
                    ("BROKEN", "🔴")
    return {
        "components": components,
        "overall": overall,
        "status": status,
        "emoji": emoji,
        "weights": WEIGHTS,
    }


def health_for_target(target: str) -> dict | None:
    """Health of the most recent run for a target (vs its predecessor)."""
    runs = [r for r in get_history(target, limit=6) if r.get("mode") != "demo"]
    if not runs:
        return None
    prev = runs[0] if len(runs) > 1 else None
    return health_score(runs[-1], prev)


# --------------------------------------------------------------------------
# Scraper Doctor — diagnosis layer
# --------------------------------------------------------------------------

class Diagnosis(dict):
    """A structured doctor's report (behaves like a dict, prints nicely)."""

    def summary(self) -> str:
        lines = [
            "SCRAPER DOCTOR",
            "-" * 46,
            "",
            "Problem:",
            f"  {self['problem']}",
            "",
            "Evidence:",
        ]
        for item in self["evidence"]:
            mark = "✓" if item.startswith("+") else "✗"
            lines.append(f"  {mark} {item[2:] if item[:2] in ('+ ', '- ') else item}")
        lines += [
            "",
            "Diagnosis:",
            f"  {self['diagnosis']}",
            "",
            "Action:",
            f"  {self['action']}",
            "",
            f"Confidence: {self['confidence']:.0f}%",
        ]
        if self.get("heal_prompt"):
            lines += ["", "Recommended heal prompt:", f'  "{self["heal_prompt"]}"']
        return "\n".join(lines)


def diagnose(current_run: dict, previous_run_rec: dict | None = None) -> Diagnosis:
    """Inspect a failed/degraded run against its baseline and produce a report."""
    prof = current_run.get("profile", current_run)
    fields = prof.get("fields", {})
    target_label = TARGETS.get(current_run.get("target"), {}).get("label", "target site")
    broken = [(n, f) for n, f in sorted(fields.items()) if f.get("pct", 0) < 95]
    working = [n for n, f in sorted(fields.items()) if f.get("pct", 100) >= 95]

    evidence = [
        "+ Page loaded, extraction returned %d records" % prof.get("n_records", 0),
    ]
    evidence += [f"+ {name} extraction works ({f['pct']:.0f}%)" for name, f in sorted(fields.items()) if f.get('pct', 0) >= 95]
    evidence += [f"- {name} missing/broken ({f['valid']}/{f['total']})" for name, f in broken]

    if broken and working:
        diagnosis = ("Selector/layout drift: page structure changed so that "
                     + ", ".join(n for n, _ in broken)
                     + " no longer match while other fields still extract fine.")
        action = "Request Collector repair (heal) scoped to the broken fields."
        confidence = 94.0
        scope = ", ".join(n for n, _ in broken)
        heal_prompt = (
            f"The {target_label} extraction has drifted. Fields currently failing: "
            f"{scope}. Fields still working: {', '.join(working)}. Re-inspect "
            f"{TARGETS.get(current_run.get('target'), {}).get('url', 'the site')} and repair ONLY "
            f"the broken selectors ({scope}) so every record again returns all of: "
            f"{', '.join(REQUIRED_FIELDS)} with correct types. Do not disturb the working fields."
        )
    elif broken and not working:
        diagnosis = "Full extraction failure — likely major DOM/layout change or bot-wall."
        action = "Request full Collector repair."
        confidence = 80.0
        heal_prompt = (
            f"The {target_label} collector returned {prof.get('n_records', 0)} records but every "
            f"required field ({', '.join(REQUIRED_FIELDS)}) is empty or mistyped. Re-inspect the "
            f"site and rebuild the extraction so each record returns all fields with correct types."
        )
    elif prof.get("n_records", 0) == 0:
        diagnosis = "Collector returned no records — layout change broke the record selector itself."
        action = "Request Collector repair targeting the record container selector."
        confidence = 88.0
        heal_prompt = (
            f"The {target_label} collector returned zero records. Re-inspect the site: the record/list "
            f"container selector likely changed. Rebuild extraction to return all visible items."
        )
    else:
        diagnosis = "No schema problems detected; fields within tolerance."
        action = "No repair needed."
        confidence = 99.0
        heal_prompt = ""

    if previous_run_rec is not None and broken:
        pf = previous_run_rec.get("profile", {}).get("fields", {})
        dropped = [
            f"{n} ({pf.get(n, {}).get('pct', 100.0):.0f}% -> {f.get('pct', 0.0):.0f}%)"
            for n, f in broken if n in pf
        ]
        if dropped:
            diagnosis += (" Historical comparison confirms regression: " + ", ".join(dropped) + ".")
            confidence = min(99.0, confidence + 4.0)

    return Diagnosis({
        "problem": "; ".join(f"{n} at {f.get('pct', 0):.0f}% ({f.get('valid', 0)}/{f.get('total', 0)})"
                             for n, f in broken) or "none — schema healthy",
        "evidence": evidence,
        "diagnosis": diagnosis,
        "action": action,
        "confidence": confidence,
        "heal_prompt": heal_prompt,
    })


# --------------------------------------------------------------------------
# healing version history (+ rollback bookkeeping)
# --------------------------------------------------------------------------

def record_version(collector_id: str, reason: str, prompt: str,
                   health_before: float, health_after: float, accepted: bool,
                   extra: dict | None = None) -> dict:
    versions = _read_json(VERSIONS_FILE, {})
    hist = versions.setdefault(collector_id, [])
    entry = {
        "version": len(hist) + 1,
        "timestamp": utcnow(),
        "reason": reason,
        "health_before": health_before,
        "health_after": health_after,
        "accepted": bool(accepted),
        "prompt": prompt,
    }
    if extra:
        entry.update(extra)
    hist.append(entry)
    _write_json(VERSIONS_FILE, versions)
    return entry


def versions_for(collector_id: str) -> list:
    return _read_json(VERSIONS_FILE, {}).get(collector_id, [])


def latest_version(collector_id: str) -> int:
    return len(versions_for(collector_id))


def seed_baseline_version(collector_id: str, label: str = "Initial scraper"):
    """Ensure v1 exists so history reads sensibly from the first heal onward."""
    hist = versions_for(collector_id)
    if not hist:
        record_version(collector_id, label, "(baseline collector created in Scraper Studio)",
                       health_before=0.0, health_after=None, accepted=True)


# --------------------------------------------------------------------------
# event log
# --------------------------------------------------------------------------

def log_event(kind: str, message: str, **extra) -> dict:
    events = _read_json(EVENTS_FILE, [])
    event = {"ts": utcnow(), "kind": kind, "message": message}
    if extra:
        event.update(extra)
    events.append(event)
    _write_json(EVENTS_FILE, events[-1000:])
    return event


def recent_events(limit: int = 20) -> list:
    return _read_json(EVENTS_FILE, [])[-limit:]
