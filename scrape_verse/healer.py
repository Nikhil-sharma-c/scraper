"""Healing orchestrator: run -> validate -> compare -> diagnose -> heal -> re-run
-> verify, with automatic acceptance (health must improve) and rollback
bookkeeping via the version history.

Cloud mode shells out to `bdata`; local mode calls scrape_verse.local_extract.
Demo mode replays bundled HTML snapshots through the same pipeline.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from . import core
from .core import (Diagnosis, TARGETS, compare, diagnose, health_score,
                   log_event, record_version)

ROOT = core.ROOT
DEMO_DIR = os.path.join(ROOT, "demo")


# --------------------------------------------------------------------------
# runners
# --------------------------------------------------------------------------

def run_cloud(target: str = "hackernews", out_path: str | None = None) -> str:
    """Run a Bright Data collector; returns path to result JSON."""
    t = TARGETS[target]
    out = os.path.abspath(out_path or os.path.join(ROOT, f"{target}_result.json"))
    cmd = ["bdata", "scraper", "run", t["collector"], t["url"], "--json", "-o", out]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"bdata scraper run failed:\n{proc.stdout}\n{proc.stderr}")
    return out


def heal_cloud(collector_id: str, prompt: str) -> None:
    cmd = ["bdata", "scraper", "heal", collector_id, prompt,
           "--auto-approve", "--auto-save"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"bdata scraper heal failed:\n{proc.stdout}\n{proc.stderr}")


def run_local(target: str = "hackernews", out_path: str | None = None) -> str:
    from .local_extract import HN_URL, run_local as _run_local
    t = TARGETS[target]
    url = t["url"] if target == "hackernews" else t.get("url")
    payload = _run_local(HN_URL)
    out = os.path.abspath(out_path or os.path.join(ROOT, f"{target}_result_local.json"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out


def run_demo(snapshot_name: str, out_path: str | None = None) -> str:
    """Replay a bundled HTML snapshot through the local extractor."""
    from .local_extract import extract
    snap = os.path.join(DEMO_DIR, snapshot_name)
    if not os.path.exists(snap):
        if os.path.exists(snapshot_name):     # allow paths outside demo/
            snap = snapshot_name
        else:
            raise FileNotFoundError(
                f"snapshot not found: {snap} (available: "
                f"{', '.join(sorted(f for f in os.listdir(DEMO_DIR) if f.endswith('.html')))})")
    with open(snap, encoding="utf-8") as f:
        html_text = f.read()
    stories = extract(html_text)
    payload = [{"stories": stories, "product_page_url": "demo-replay://" + snapshot_name,
                "input": snapshot_name}]
    out = os.path.abspath(out_path or os.path.join(ROOT, "data",
                                                   f"demo_{os.path.splitext(snapshot_name)[0]}.json"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out


# --------------------------------------------------------------------------
# pipeline pieces
# --------------------------------------------------------------------------

def evaluate(result_path: str, target: str, mode: str, source: str,
             note: str = "") -> dict:
    """Save a run, compare to previous, score health. Returns context dict."""
    run = core.save_run(result_path, source=source, mode=mode, target=target, note=note)
    prev = core.previous_run(run)
    drift = []
    if prev is not None:
        drift = compare(prev["profile"], run["profile"])
        if drift:
            log_event("drift", "Schema drift detected: "
                      + "; ".join(f"{d['field']} {d['prev_pct']:.0f}%->{d['new_pct']:.0f}%"
                                  for d in drift),
                      target=target, severity=max(d["severity"] for d in drift))
    health = health_score(run, prev)
    return {"run": run, "previous": prev, "drift": drift, "health": health}


def print_drift_banner(drift: list):
    print()
    print("⚠️  EXTRACTION DRIFT DETECTED")
    for d in drift:
        if d["kind"] == "field_drop":
            print(f"   {d['field']}: {d['prev_pct']:.0f}% → {d['new_pct']:.0f}%"
                  f"  ({'CRITICAL' if d['severity'] == 'critical' else 'warning'})")
        elif d["kind"] == "record_count_drop":
            print(f"   records: {d['detail']}  ({d['new_pct']:.1f}% of previous)")
        else:
            print(f"   {d.get('detail') or d['kind']}")
    print("   Likely DOM/layout change.")


def self_heal(target: str = "hackernews", mode: str = "auto", max_attempts: int = 2,
              auto_approve: bool = True) -> dict:
    """Full closed loop with verification + automatic rejection/rollback.

    Demo narratives: --mode "demo:hn_v2.html->hn_v3.html" runs the BROKEN
    snapshot as baseline, and the FIXED snapshot after the (simulated)
    repair — so the verify step can genuinely accept the repair.
    """
    if "->" in mode:
        base_mode, repaired_mode = mode.split("->", 1)
        # keep the demo: prefix on the repaired leg unless it names its own mode
        if base_mode.startswith("demo:") and "://" not in repaired_mode \
                and not repaired_mode.startswith(("demo:", "cloud", "local")):
            repaired_mode = "demo:" + repaired_mode
    else:
        base_mode = repaired_mode = mode
    t = TARGETS[target]

    # -- 1. baseline run ---------------------------------------------------
    print(f"=== [1/6] Running {t['label']} ({base_mode} mode) ===")
    result_path = _dispatch_run(base_mode, target)
    ctx = evaluate(result_path, target, mode, source="self-heal baseline")
    baseline_health = ctx["health"]["overall"]
    print(health_line(ctx))

    # healthy on first pass? nothing to do
    needs_repair = bool(ctx["drift"]) or ctx["health"]["status"] != "HEALTHY"
    if not needs_repair:
        print("\n✅ Schema healthy — no repair needed.")
        return {"accepted": True, "needed": False, "baseline": ctx}

    collector_id = t["collector"]
    core.seed_baseline_version(collector_id)

    attempt = 0
    current = ctx
    while needs_repair and attempt < max_attempts:
        attempt += 1
        # -- diagnose ------------------------------------------------------
        print(f"\n=== [3/6] 🤖 Scraper Doctor diagnosing (attempt {attempt}/{max_attempts}) ===")
        dx = diagnose(current["run"], current["previous"])
        print(dx.summary())
        log_event("diagnosis", f"{dx['diagnosis']} (confidence {dx['confidence']:.0f}%)",
                  target=target)
        if not dx["heal_prompt"]:
            break

        # -- heal ----------------------------------------------------------
        print(f"\n=== [4/6] Repairing Collector {collector_id} ===")
        log_event("heal_started", f"Healing {collector_id}: {dx['problem']}", target=target)
        if base_mode.startswith("demo:"):
            print("(demo mode: repair applied to the replayed page — selectors restored)")
        elif mode in ("cloud", "auto"):
            heal_cloud(collector_id, dx["heal_prompt"])
        else:
            print("(local mode: repair is simulated — selectors are code-side)")

        # -- re-run --------------------------------------------------------
        print("\n=== [5/6] Re-running after repair ===")
        try:
            result_path = _dispatch_run(repaired_mode, target)
        except Exception as exc:  # keep the loop alive; verify step will judge
            print(f"Re-run failed: {exc}")
            continue
        current = evaluate(result_path, target, mode, source=f"post-heal attempt {attempt}")
        post_health = current["health"]["overall"]

        # -- verify / accept / reject ---------------------------------------
        print("\n=== [6/6] Verifying repair ===")
        improved = post_health > baseline_health and not current["drift"]
        entry = record_version(
            collector_id,
            reason=dx["problem"],
            prompt=dx["heal_prompt"],
            health_before=baseline_health,
            health_after=post_health,
            accepted=improved,
            extra={"attempt": attempt, "target": target},
        )
        if improved:
            gain = post_health - baseline_health
            print(f"✅ Repair ACCEPTED — health {baseline_health}% → {post_health}% (+{gain:.0f})")
            print(f"   Recorded as v{entry['version']} in healing history.")
            log_event("repair_accepted",
                      f"Health {baseline_health}->{post_health}; recorded v{entry['version']}",
                      target=target)
            return {"accepted": True, "needed": True, "baseline": ctx, "final": current}
        else:
            print(f"❌ Repair REJECTED — health {baseline_health}% → {post_health}%")
            print(f"   Rolling back: keeping pre-heal behavior (v{latest_stable(t['collector'])}).")
            log_event("repair_rejected",
                      f"Health {baseline_health}->{post_health}; rejected v{entry['version']}",
                      target=target)
            baseline_health = post_health  # next attempt judged against this

    print("\n⚠️  Drift persists after healing attempts — manual review needed.")
    return {"accepted": False, "needed": True, "baseline": ctx, "final": current}


def latest_stable(collector_id: str) -> int:
    versions = [v for v in core.versions_for(collector_id) if v.get("accepted")]
    return versions[-1]["version"] if versions else 1


def _dispatch_run(mode: str, target: str) -> str:
    if mode == "cloud":
        return run_cloud(target)
    if mode == "local":
        return run_local(target)
    if mode.startswith("demo:"):
        return run_demo(mode.split(":", 1)[1])
    # auto: prefer cloud, fall back to local
    try:
        return run_cloud(target)
    except Exception as exc:
        print(f"(cloud run unavailable: {exc.__class__.__name__}) falling back to local mode")
        return run_local(target)


def health_line(ctx: dict) -> str:
    h = ctx["health"]
    comps = h["components"]
    return (
        f"\nSCRAPER HEALTH — {h['emoji']} {h['status']} {h['overall']}%\n"
        f"{'-'*40}\n"
        f"Schema validity        {comps['schema_validity']:>5}%\n"
        f"Field completeness     {comps['field_completeness']:>5}%\n"
        f"Record count           {comps['record_count']:>5}%\n"
        f"URL validity           {comps['url_validity']:>5}%\n"
        f"Hist. consistency      {comps['historical_consistency']:>5}%\n"
        f"{'-'*40}\n"
        f"Overall                {h['overall']:>5}%"
    )
