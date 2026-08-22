"""Generate a static HTML dashboard from data/runs.json + events.json."""
from __future__ import annotations

import html
import os

from . import core


def _status_chip(status: str) -> str:
    color = {"HEALTHY": "#16a34a", "DEGRADED": "#d97706", "BROKEN": "#dc2626"}.get(
        status, "#6b7280")
    dot = {"HEALTHY": "🟢", "DEGRADED": "🟡", "BROKEN": "🔴"}.get(status, "⚪")
    return f'<span style="color:{color};font-weight:600">{dot} {status}</span>'


def render(out_path: str | None = None) -> str:
    out_path = out_path or os.path.join(core.ROOT, "dashboard.html")
    targets = list(core.TARGETS.keys())
    cards = []
    for t in targets:
        label = core.TARGETS[t]["label"]
        h = core.health_for_target(t)
        if h is None:
            cards.append(f"""
        <div class="card">
          <h3>{html.escape(label)}</h3>
          <p class="muted">No runs recorded yet</p>
        </div>""")
            continue
        c = h["components"]
        bars = "".join(
            f'<div class="bar-row"><span>{k.replace("_", " ").title()}</span>'
            f'<div class="bar"><div class="fill" style="width:{v}%"></div></div><b>{v:.0f}%</b></div>'
            for k, v in c.items())
        cards.append(f"""
        <div class="card">
          <h3>{html.escape(label)} {_status_chip(h['status'])}</h3>
          <div class="score">{h['overall']:.0f}%</div>
          {bars}
        </div>""")

    events = core.recent_events(12)
    ev_rows = "".join(
        f"<tr><td class='mono'>{e['ts'][11:19]}</td><td>{html.escape(e['kind'])}</td>"
        f"<td>{html.escape(e['message'])}</td></tr>"
        for e in reversed(events))

    # healing stats
    all_versions = []
    for cid, hist in core._read_json(core.VERSIONS_FILE, {}).items():
        all_versions.extend(hist)
    repairs = [v for v in all_versions if v.get("health_after") is not None]
    accepted = [v for v in repairs if v.get("accepted")]
    success_rate = round(100.0 * len(accepted) / len(repairs), 0) if repairs else None
    avg_gain = (sum(v["health_after"] - v["health_before"] for v in accepted) / len(accepted)
                if accepted else None)

    stats = f"""
      <div class="stat"><div class="num">{len(core.get_history(limit=1000))}</div><div>runs recorded</div></div>
      <div class="stat"><div class="num">{success_rate if success_rate is not None else '—'}%</div><div>repair success</div></div>
      <div class="stat"><div class="num">{('+' + format(avg_gain, '.0f')) if avg_gain is not None else '—'}</div><div>avg health gain</div></div>
      <div class="stat"><div class="num">{len(all_versions)}</div><div>collector versions</div></div>"""

    html_text = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>Scrape-Verse Dashboard</title>
<style>
 body {{ font-family: ui-sans-serif, system-ui, sans-serif; background:#0b1020; color:#e5e7eb;
        margin:0; padding:2rem; }}
 h1 {{ letter-spacing:.02em; }} .muted {{ color:#94a3b8; }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:1rem; margin-top:1rem; }}
 .card {{ background:#111827; border:1px solid #1f2937; border-radius:14px; padding:1.2rem 1.4rem; }}
 .score {{ font-size:2.6rem; font-weight:700; margin:.2rem 0 .8rem; }}
 .bar-row {{ display:flex; align-items:center; gap:.6rem; margin:.35rem 0; font-size:.85rem; }}
 .bar-row span {{ width:150px; color:#9ca3af; }}
 .bar {{ flex:1; height:8px; background:#1f2937; border-radius:99px; overflow:hidden; }}
 .fill {{ height:100%; background:linear-gradient(90deg,#22d3ee,#34d399); }}
 table {{ border-collapse:collapse; width:100%; margin-top:1rem; font-size:.88rem; }}
 td, th {{ text-align:left; padding:.45rem .6rem; border-bottom:1px solid #1f2937; vertical-align:top; }}
 th {{ color:#9ca3af; font-weight:500; }}
 .stats {{ display:flex; gap:1rem; flex-wrap:wrap; margin-top:1rem; }}
 .stat {{ background:#111827; border:1px solid #1f2937; border-radius:12px; padding:.8rem 1.3rem; text-align:center; min-width:120px; }}
 .num {{ font-size:1.5rem; font-weight:700; color:#22d3ee; }}
 .mono {{ font-family:ui-monospace,monospace; color:#94a3b8; }}
</style></head><body>
<h1>🪐 SCRAPE-VERSE</h1>
<p class="muted">Self-healing scraping agent — model-agnostic · cloud (Bright Data) + local mode</p>
<div class="grid">{ ''.join(cards)}
</div>
<h2 style="margin-top:2rem">Healing Stats</h2>
<div class="stats">{stats}
</div>
<h2 style="margin-top:2rem">Recent Events</h2>
<table><tr><th>time (UTC)</th><th>event</th><th>detail</th></tr>
{ev_rows}
</table>
<p class="muted" style="margin-top:2rem">Static snapshot — regenerate with <code>sv dashboard</code>.</p>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return out_path
