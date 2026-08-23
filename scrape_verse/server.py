"""Scrape-Verse local web GUI + JSON API (stdlib only).

    python -m scrape_verse.server            # http://127.0.0.1:8765

Serves gui/index.html plus a JSON API over the engine:

    GET  /api/targets            registered targets + latest health each
    GET  /api/health?target=X    health of the latest run for X
    GET  /api/events?limit=N     recent event log
    GET  /api/runs?limit=N       run history
    GET  /api/versions           healing version history (all collectors)
    GET  /api/result/<run_id>    records of a stored run
    POST /api/scrape             {"url","query"} -> {job_id}  (async)
    GET  /api/job/<id>           job status / result
    POST /api/rerun              {"target"} -> {job_id}  re-run pinned collector
    GET  /api/data/<target>      records of the latest run for a target
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import core

GUI_DIR = os.path.join(core.ROOT, "gui")
PORT = int(os.environ.get("SV_PORT", "8765"))
CREATE_TIMEOUT = 60 * 45          # scraper create can take 5–25+ min
MAX_RECORDS_IN_RESULT = 500

# --------------------------------------------------------------------------
# async job manager — arbitrary sites go through `bdata scraper create`
# --------------------------------------------------------------------------

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _get_job(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def _set_job(job_id: str, **fields):
    with _JOBS_LOCK:
        _JOBS.setdefault(job_id, {}).update(fields)


def _run_bdata(args: list, timeout: int):
    from .healer import _find_bdata
    import subprocess
    return subprocess.run([_find_bdata(), *args],
                          capture_output=True, text=True, timeout=timeout)


def _evaluate(result_path: str, target_key: str, mode: str, source: str) -> dict:
    """Route through the standard pipeline so history/drift/health stay consistent."""
    from .healer import evaluate
    return evaluate(result_path, target_key, mode=mode, source=source)


def _preview(result_path: str, target_key: str = "hackernews", cap: int = 12) -> list[dict]:
    try:
        with open(result_path, encoding="utf-8") as f:
            raw = json.load(f)
        records = core.extract_records(raw, target_key)
        flat = []
        for rec in records[:cap]:
            if isinstance(rec, dict):
                flat.append({k: (v if isinstance(v, (str, int, float)) else str(v))
                             for k, v in rec.items()})
        return flat
    except Exception:
        return []


def _register_dynamic_target(job_id: str, url: str, query: str, collector_id: str = "",
                             state: str = "building", backend: str = "agent") -> dict:
    """One card per URL — register/update a dynamic target for the fleet view."""
    from urllib.parse import urlparse as _up
    host = (_up(url).netloc or url).replace("www.", "")[:28] or "job"
    key = "site_" + uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:8]
    core.register_target(key, label=host, url=url,
                         collector_id=collector_id, query=query,
                         backend=backend)
    core.set_target_state(key, state=state, job_id=job_id,
                          error=None if state not in ("error",) else "")
    return key


def _run_scrape_job(job_id: str, url: str, query: str,
                    backend: str = "agent", api_url: str = "",
                    api_header: str = "") -> None:
    try:
        if backend == "api":
            _run_api_job(job_id, url, query, api_url, api_header)
            return

        # ---- Bright Data agent path: create -> run -> evaluate -----------
        _set_job(job_id, status="creating",
                 message="Bright Data's AI is learning this website…")
        proc = _run_bdata(["scraper", "create", url, query[:500],
                           "--name", f"sv_{int(time.time())}", "--json"],
                          timeout=CREATE_TIMEOUT)
        out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        if proc.returncode != 0:
            tail = out[-400:] or "(no output)"
            # Bright Data's builder failed for this site — surface it honestly.
            m = re.search(r"c_[a-z0-9]+", out)
            hint = f" Half-built collector {m.group(0)} — delete it in the dashboard." if m else ""
            _set_job(job_id, status="error",
                     message=f"scraper create failed:{hint} {tail[-300:]}")
            return
        collector_id = None
        for line in reversed(proc.stdout.strip().splitlines() or []):
            line = line.strip()
            if line.startswith("{"):
                try:
                    info = json.loads(line)
                    collector_id = info.get("collector_id") or info.get("id")
                    if collector_id:
                        break
                except json.JSONDecodeError:
                    continue
        if not collector_id:
            _set_job(job_id, status="error",
                     message=f"could not parse collector id; CLI said: {out[-200:]}")
            return

        target_key = _register_dynamic_target(job_id, url, query, collector_id,
                                              state="running")
        _set_job(job_id, status="running", target=target_key,
                 message=f"Collector {collector_id} ready — running…")

        out_path = os.path.join(core.DATA_DIR, f"jobs_{job_id}.json")
        proc = _run_bdata(["scraper", "run", collector_id, url,
                           "--json", "-o", out_path], timeout=900)
        if proc.returncode != 0:
            core.set_target_state(target_key, state="error", job_id=job_id)
            _set_job(job_id, status="error",
                     message=f"scraper run failed: {((proc.stderr or '') + (proc.stdout or ''))[-400:]}")
            return

        ctx = _evaluate(out_path, target_key, mode="cloud", source=f"gui job: {query[:80]}")
        n = ctx["run"]["profile"]["n_records"]
        core.set_target_state(target_key, state="ready" if n else "no_data",
                              job_id=job_id, collector_id=collector_id)
        _set_job(job_id, status="done", run_id=ctx["run"]["id"], result_file=out_path,
                 collector_id=collector_id, target=target_key,
                 summary=(f"{ctx['health']['overall']}% · {ctx['health']['status']} · "
                          f"{n} records"),
                 drift=ctx["drift"], health=ctx["health"],
                 preview=_preview(out_path, target_key))
        core.log_event("gui_scrape",
                       f"GUI job done: {url} → {n} records, "
                       f"{len(ctx['drift'])} drift findings",
                       target=target_key)
    except Exception as exc:
        _set_job(job_id, status="error", message=f"{exc.__class__.__name__}: {exc}")


def _run_api_job(job_id: str, url: str, query: str,
                 api_url: str, api_header: str) -> None:
    """Bring-your-own backend: POST {url, query} to the user's endpoint.

    Expected response is JSON containing an array of record objects — any of
    results/data/items/rows/records/movies/products/posts/listings keys, a
    top-level list, or the first list-of-dicts anywhere (same tolerance as
    cloud payloads). The result then flows through the SAME validate →
    profile → health-score pipeline as agent jobs.
    """
    import urllib.request
    import urllib.error

    def _fail(msg: str):
        _set_job(job_id, status="error", message=msg)

    target_key = _register_dynamic_target(job_id, url, query,
                                          state="running", backend="api")
    _set_job(job_id, status="running", target=target_key,
             message=f"Calling your API… {api_url[:60]}")

    payload = json.dumps({"url": url, "query": query[:500]}).encode()
    req = urllib.request.Request(api_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_header:
        name, _, value = api_header.partition(":")
        if not value:
            return _fail("custom header must look like 'Name: value'")
        req.add_header(name.strip(), value.strip())

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        return _fail(f"your API returned HTTP {e.code}")
    except Exception as exc:
        return _fail(f"could not reach your API ({exc.__class__.__name__}: "
                     f"{str(exc)[:120]})")

    out_path = os.path.join(core.DATA_DIR, f"jobs_{job_id}.json")
    with open(out_path, "wb") as f:
        f.write(body)

    # sanity: does the payload actually contain records?
    try:
        probe = core.extract_records(json.loads(body.decode()), target_key)
    except Exception:
        probe = []
    if not probe:
        return _fail("API responded, but no usable records were found in the "
                     "JSON (expected a list of objects under a key like "
                     "'data', 'items', 'results'…)")

    ctx = _evaluate(out_path, target_key, mode="api", source=f"custom API job: {query[:80]}")
    n = ctx["run"]["profile"]["n_records"]
    core.set_target_state(target_key, state="ready" if n else "no_data",
                          job_id=job_id)
    _set_job(job_id, status="done", run_id=ctx["run"]["id"], result_file=out_path,
             target=target_key,
             summary=(f"{ctx['health']['overall']}% · {ctx['health']['status']} · "
                      f"{n} records"),
             drift=ctx["drift"], health=ctx["health"],
             preview=_preview(out_path, target_key))
    core.log_event("gui_scrape",
                   f"GUI custom-API job done: {url} → {n} records",
                   target=target_key)


def _rerun_job(job_id: str, target_key: str) -> None:
    """Re-run an existing pinned collector (no rebuild) and rescore."""
    try:
        t = core.get_target(target_key)
        cid, url = t.get("collector", ""), t.get("url", "")
        if not cid.startswith("c_"):
            _set_job(job_id, status="error",
                     message="this target has no cloud collector pinned yet")
            return
        core.set_target_state(target_key, state="running", job_id=job_id)
        _set_job(job_id, status="running", target=target_key,
                 message=f"Re-running collector {cid}…")
        out_path = os.path.join(core.DATA_DIR, f"jobs_{job_id}.json")
        proc = _run_bdata(["scraper", "run", cid, url, "--json", "-o", out_path],
                          timeout=900)
        if proc.returncode != 0:
            core.set_target_state(target_key, state="error", job_id=job_id,
                                  error=((proc.stderr or "") + (proc.stdout or ""))[-300:])
            _set_job(job_id, status="error",
                     message=f"scraper run failed: {((proc.stderr or '') + (proc.stdout or ''))[-400:]}")
            return
        ctx = _evaluate(out_path, target_key, mode="cloud", source="GUI re-run")
        n = ctx["run"]["profile"]["n_records"]
        core.set_target_state(target_key, state="ready" if n else "no_data",
                              job_id=job_id, collector_id=cid)
        _set_job(job_id, status="done", run_id=ctx["run"]["id"], result_file=out_path,
                 collector_id=cid, target=target_key,
                 summary=(f"{ctx['health']['overall']}% · {ctx['health']['status']} · "
                          f"{n} records"),
                 drift=ctx["drift"], health=ctx["health"],
                 preview=_preview(out_path, target_key))
        core.log_event("gui_scrape",
                       f"GUI re-run: {url} → {n} records",
                       target=target_key)
    except Exception as exc:
        _set_job(job_id, status="error", message=f"{exc.__class__.__name__}: {exc}")


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "ScrapeVerse/0.3"

    # -- helpers ----------------------------------------------------------
    def _json(self, obj, code: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, rel_path: str):
        path = os.path.normpath(os.path.join(GUI_DIR, rel_path))
        if not path.startswith(GUI_DIR) or not os.path.isfile(path):
            self._json({"error": "not found"}, 404)
            return
        ctype = {".html": "text/html", ".js": "text/javascript",
                 ".css": "text/css", ".svg": "image/svg+xml"}.get(
                     os.path.splitext(path)[1], "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 1_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return {}

    def log_message(self, fmt, *args):   # quiet
        pass

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            return self._file("index.html")
        if route.startswith("/static/"):
            return self._file(route[len("/static/"):])

        if route == "/api/targets":
            out = []
            for key in core.all_target_keys():
                t = core.get_target(key)
                st = core.get_target_state(key)
                h = core.health_for_target(key)
                runs = [r for r in core.get_history(target=key, limit=2)
                        if r.get("mode") != "demo"]
                last = runs[0] if runs else None
                out.append({
                    "key": key, "label": t["label"], "url": t["url"],
                    "collector": t["collector"], "state": st.get("state"),
                    "error": st.get("error"), "health": h,
                    "query": t.get("query", ""),
                    "backend": t.get("backend", "agent"),
                    "last_run": ({
                        "id": last["id"], "when": last["timestamp"],
                        "records": last["profile"]["n_records"],
                    } if last else None),
                })
            return self._json({"targets": out})

        if route == "/api/health":
            key = (qs.get("target") or ["hackernews"])[0]
            h = core.health_for_target(key)
            return self._json({"target": key, "health": h})

        if route == "/api/events":
            limit = min(int((qs.get("limit") or ["25"])[0]), 200)
            return self._json({"events": core.recent_events(limit)})

        if route == "/api/runs":
            limit = min(int((qs.get("limit") or ["20"])[0]), 100)
            runs = []
            for r in core.get_history(limit=limit):
                prof = r["profile"]
                runs.append({
                    "id": r["id"], "timestamp": r["timestamp"],
                    "target": r.get("target"), "mode": r.get("mode"),
                    "source": r.get("source"),
                    "n_records": prof["n_records"],
                    "fields": {k: v["pct"] for k, v in prof["fields"].items()},
                })
            return self._json({"runs": runs})

        if route == "/api/versions":
            versions = {}
            for cid, hist in core._read_json(core.VERSIONS_FILE, {}).items():
                versions[cid] = hist
            return self._json({"versions": versions})

        m_result = route.startswith("/api/result/")
        if m_result:
            run_id = route[len("/api/result/"):]
            run = core.load_run(run_id)
            if not run or not os.path.isfile(run.get("result_file", "")):
                return self._json({"error": "run or result file not found"}, 404)
            with open(run["result_file"], encoding="utf-8") as f:
                raw = json.load(f)
            records = core.extract_records(raw, run.get("target", "hackernews"))
            return self._json({"run_id": run_id,
                               "records": records[:MAX_RECORDS_IN_RESULT]})

        m_data = route.startswith("/api/data/")
        if m_data:
            key = route[len("/api/data/"):]
            runs = [r for r in core.get_history(target=key, limit=1)
                    if r.get("mode") != "demo"]
            if not runs:
                return self._json({"error": "no completed runs for this target yet"}, 404)
            run = core.load_run(runs[0]["id"])
            if not run or not os.path.isfile(run.get("result_file", "")):
                return self._json({"error": "result file missing"}, 404)
            with open(run["result_file"], encoding="utf-8") as f:
                raw = json.load(f)
            t = core.get_target(key)
            return self._json({
                "target": key, "label": t["label"], "url": t["url"],
                "query": t.get("query", ""),
                "when": run["timestamp"],
                "records": core.extract_records(raw, key)[:MAX_RECORDS_IN_RESULT],
            })

        if route.startswith("/api/job/"):
            job = _get_job(route[len("/api/job/"):])
            return (self._json(job) if job else self._json({"error": "unknown job"}, 404))

        return self._json({"error": "unknown route"}, 404)

    # -- POST ---------------------------------------------------------------
    def do_POST(self):
        route = urlparse(self.path).path
        body = self._body()

        if route == "/api/scrape":
            url = (body.get("url") or "").strip()
            query = (body.get("query") or "").strip()
            backend = (body.get("backend") or "agent").strip().lower()
            api_url = (body.get("api_url") or "").strip()
            api_header = (body.get("api_header") or "").strip()
            if not url.startswith(("http://", "https://")):
                return self._json({"error": "url must start with http(s)://"}, 400)
            if not query:
                return self._json({"error": "query is required (what should be scraped?)"},
                                  400)
            if backend not in ("agent", "api"):
                return self._json({"error": "backend must be 'agent' or 'api'"}, 400)
            if backend == "api" and not api_url.startswith(("http://", "https://")):
                return self._json({"error": "a valid API endpoint URL is required "
                                            "for the custom API backend"}, 400)
            job_id = uuid.uuid4().hex[:12]
            # card appears immediately in the fleet view while building
            _register_dynamic_target(job_id, url, query,
                                     state="building" if backend == "agent" else "running",
                                     backend=backend)
            _set_job(job_id, status="queued", message="queued")
            threading.Thread(target=_run_scrape_job,
                             args=(job_id, url, query, backend, api_url, api_header),
                             daemon=True).start()
            return self._json({"job_id": job_id}, 202)

        if route == "/api/rerun":
            key = (body.get("target") or "").strip()
            if not core.get_target(key):
                return self._json({"error": "unknown target"}, 404)
            job_id = uuid.uuid4().hex[:12]
            _set_job(job_id, status="queued", message="queued", target=key)
            threading.Thread(target=_rerun_job, args=(job_id, key),
                             daemon=True).start()
            return self._json({"job_id": job_id}, 202)

        return self._json({"error": "unknown route"}, 404)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Scrape-Verse GUI → http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
