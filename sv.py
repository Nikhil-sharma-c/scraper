#!/usr/bin/env python3
"""sv — Scrape-Verse command line.

Natural-language-ish entry point for the self-healing pipeline:

    sv run [--mode cloud|local|demo:<snapshot>] [--target hackernews]
    sv health [--target hackernews] [--json]
    sv doctor [--run RUN_ID] [--target hackernews]
    sv compare [--limit N]
    sv heal [--mode ...] [--max-attempts N]
    sv history [--target hackernews] [--limit N]
    sv events [--limit N]
    sv demo <snapshot.html>
    sv dashboard [-o FILE]

Exit codes: 0 healthy / repaired OK, 1 drift unresolved or error.
"""
from __future__ import annotations

import argparse
import json
import sys

from scrape_verse import core, healer


def cmd_run(args):
    result_path = healer._dispatch_run(args.mode if args.mode != "auto" else "auto",
                                       args.target)
    ctx = healer.evaluate(result_path, args.target,
                          mode=("cloud" if args.mode == "cloud" else
                                "demo" if args.mode.startswith("demo:") else args.mode),
                          source="cli run")
    print(f"Saved run {ctx['run']['id']} ({result_path})")
    print(healer.health_line(ctx))
    if ctx["drift"]:
        healer.print_drift_banner(ctx["drift"])
        print("\nRun `sv heal` to start the repair loop.")
        return 1
    return 0


def cmd_health(args):
    if args.target and args.target != "all":
        targets = [args.target]
    else:
        targets = list(core.TARGETS.keys())
    any_unhealthy = False
    payload = {}
    for t in targets:
        h = core.health_for_target(t)
        label = core.TARGETS[t]["label"]
        if h is None:
            print(f"{label}: no runs yet")
            continue
        comps = h["components"]
        print(f"\n{label}   {h['emoji']} {h['status']}  {h['overall']}%")
        print("─" * 38)
        print(f"Schema validity        {comps['schema_validity']:>5}%")
        print(f"Field completeness     {comps['field_completeness']:>5}%")
        print(f"Record count           {comps['record_count']:>5}%")
        print(f"URL validity           {comps['url_validity']:>5}%")
        print(f"Historical consistency {comps['historical_consistency']:>5}%")
        print("─" * 38)
        print(f"Overall                {h['overall']:>5}%")
        if h["status"] != "HEALTHY":
            any_unhealthy = True
        payload[t] = h
    if args.json:
        print(json.dumps(payload, indent=2))
    return 1 if any_unhealthy else 0


def cmd_doctor(args):
    runs = core.get_history(args.target, limit=200)
    if not runs:
        print("No runs recorded yet. Run `sv run` first.")
        return 1
    run = core.load_run(args.run) if args.run else runs[-1]
    prev = core.previous_run(run)
    dx = healer.diagnose(run, prev)
    print(dx.summary())
    return 0 if dx["problem"] == "none — schema healthy" else 1


def cmd_compare(args):
    runs = core.get_history(args.target, limit=args.limit)
    if len(runs) < 2:
        print("Need at least two runs to compare.")
        return 1
    fields = core.REQUIRED_FIELDS
    header = f"{'run':<22}" + "".join(f"{f[:9]:>10}" for f in fields) + f"{'records':>9}"
    print(header)
    print("─" * len(header))
    for r in runs:
        prof = r["profile"]
        cells = "".join(f"{prof['fields'].get(f, {}).get('pct', 0):>9.0f}%" for f in fields)
        print(f"{r['id']:<22}{cells}{prof['n_records']:>9}")
    cur, prev = runs[-1], runs[-2]
    drift = core.compare(prev["profile"], cur["profile"])
    if drift:
        healer.print_drift_banner(drift)
        return 1
    print("\nNo drift between the last two runs.")
    return 0


def cmd_heal(args):
    outcome = healer.self_heal(target=args.target, mode=args.mode,
                               max_attempts=args.max_attempts)
    return 0 if outcome.get("accepted") else 1


def cmd_history(args):
    collector_id = core.TARGETS[args.target]["collector"]
    hist = core.versions_for(collector_id)
    if not hist:
        print(f"No healing history yet for {collector_id}.")
        return 0
    print(f"Healing version history — Collector {collector_id}")
    print("─" * 60)
    for v in hist:
        status = "✅" if v.get("accepted") else "❌ rejected"
        after = v.get("health_after")
        after_s = f"{after:.0f}%" if isinstance(after, (int, float)) else "—"
        before = v.get("health_before") or 0
        print(f"v{v['version']:<3} {v['timestamp']:<21} {status}")
        print(f"     reason: {v['reason'][:70]}")
        print(f"     health: {before:.0f}% → {after_s}")
    return 0


def cmd_events(args):
    for e in core.recent_events(args.limit):
        print(f"{e['ts'][11:19]}  {e['kind']:<18} {e['message']}")
    return 0


def cmd_demo(args):
    snap = args.snapshot
    if not snap.endswith(".html"):
        snap += ".html"
    mode = f"demo:{snap}"
    result_path = healer.run_demo(snap)
    ctx = healer.evaluate(result_path, "hackernews", mode="demo",
                          source=f"demo replay: {snap}")
    print(f"Replayed {snap}")
    print(healer.health_line(ctx))
    if ctx["drift"]:
        healer.print_drift_banner(ctx["drift"])
        print("\n🤖 Doctor diagnosing...")
        dx = healer.diagnose(ctx["run"], ctx["previous"])
        print(dx.summary())
        print("\nIn a live incident this diagnosis would now drive `bdata scraper heal`.")
        print("Continue the story:  sv heal --mode demo:" + snap)
        return 1
    print("\n✅ Replay matches the healthy schema — no drift vs previous run.")
    return 0


def cmd_dashboard(args):
    from scrape_verse import dashboard
    path = dashboard.render(args.output)
    print(f"Dashboard written: {path}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sv", description="Scrape-Verse control CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--target", default="hackernews")

    sp = sub.add_parser("run", help="run scraper + validate + score")
    sp.add_argument("--mode", default="auto",
                    help="cloud | local | demo:<file.html>")
    common(sp)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("health", help="show health score per target")
    sp.add_argument("--json", action="store_true")
    common(sp)
    sp.set_defaults(func=cmd_health)

    sp = sub.add_parser("doctor", help="diagnose latest (or given) run")
    sp.add_argument("--run", dest="run", default=None)
    common(sp)
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("compare", help="compare recent runs field by field")
    sp.add_argument("--limit", type=int, default=6)
    common(sp)
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("heal", help="full closed-loop heal with verify/rollback")
    sp.add_argument("--mode", default="auto")
    sp.add_argument("--max-attempts", type=int, default=2)
    common(sp)
    sp.set_defaults(func=cmd_heal)

    sp = sub.add_parser("history", help="healing version history")
    common(sp)
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser("events", help="recent event log")
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_events)

    sp = sub.add_parser("demo", help="replay a bundled HTML snapshot")
    sp.add_argument("snapshot")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("dashboard", help="(re)generate dashboard.html")
    sp.add_argument("-o", "--output", default=None)
    sp.set_defaults(func=cmd_dashboard)

    args = p.parse_args(argv)
    rc = args.func(args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
