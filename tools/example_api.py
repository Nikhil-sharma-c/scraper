"""Example "My own API" backend for Scrape-Verse's custom-API mode.

Run it:

    python tools/example_api.py            # serves http://127.0.0.1:9099/scrape

Then in the GUI pick 🔌 My own API and point it at that URL. The endpoint
receives POST {"url": ..., "query": ...} and replies with JSON containing a
list of record objects — here we just generate deterministic fake books so
you can try the flow without touching any real site.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TITLES = ["The Quiet Ledger", "Neon Harvest", "Salt & Circuitry", "A Field Guide to Ghosts",
          "Midnight Cartography", "The Last Analog Summer", "Paper Engines", "Glasshouse"]
AUTHORS = ["R. Okafor", "M. Lindqvist", "J. Barros", "A. Nakamura", "T. Whitfield"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # quiet
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length).decode())
        except Exception:
            self._send(400, {"error": "invalid JSON"})
            return
        url = str(req.get("url", ""))
        n = 8 + sum(ord(c) for c in url) % 6          # deterministic per-URL count
        books = [{
            "title": TITLES[i % len(TITLES)],
            "author": AUTHORS[i % len(AUTHORS)],
            "price": round(9.99 + (i * 3.7) % 25, 2),
            "source_page": url,
        } for i in range(n)]
        # deliberately drop some prices → completeness <100%, like real life
        for b in books[::3]:
            b["price"] = None
        self._send(200, {"results": books})

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("example API → http://127.0.0.1:9099/scrape")
    ThreadingHTTPServer(("127.0.0.1", 9099), Handler).serve_forever()
