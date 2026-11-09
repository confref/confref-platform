#!/usr/bin/env python3
"""The platform's application (decision 0003): the documents of our IRIs on id.confref.org (resolve.py, pages.py),
and on labs.confref.org the search, the APIs, the reconciliation service, the calendars and the dashboard.
Standard library only; behind nginx, which adds the kit (SSI) and serves the static site, the map and the SPARQL
endpoint.

    CR_DB=…/confref.sqlite python3 app.py

Locally (without nginx): CR_KIT_DIR=<labs site>/kit puts the kit into the pages, CR_SITE_DIR=<labs site> serves the
static site, CR_ID_BASE and CR_LABS_BASE point the links to this server.
"""

import json
import mimetypes
import os
import re
import signal
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import api
import config
import dashboard
import resolve
import search
from common import Response, error_page

ID_PATHS = re.compile(r"^/(series|event|data|datasets|ontology|dumps)(/|$)")
SITE = os.environ.get("CR_SITE_DIR")


class Handler(BaseHTTPRequestHandler):
    server_version = "confref-labs"
    sys_version = ""

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def send(self, r):
        body = r.body.encode("utf-8") if isinstance(r.body, str) else r.body
        self.send_response(r.status)
        self.send_header("Content-Type", r.ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in r.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send(Response(204, "", "text/plain", {"Access-Control-Allow-Origin": "*",
                                                   "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                                                   "Access-Control-Allow-Headers": "Content-Type, Accept"}))

    def do_GET(self, body=None):
        url = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(url.path)
        qs = urllib.parse.parse_qs(url.query)
        host = (self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "").split(":")[0].lower()
        try:
            self.send(route(host, path, qs, self.headers.get("Accept", ""), body))
        except Exception:                                   # one broken view must not take the app down
            traceback.print_exc()
            self.send(error_page(500, "Something went wrong", "The error was logged."))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(n, 2_000_000)).decode("utf-8", "replace") if n else ""
        self.do_GET(body)


def route(host, path, qs, accept, body=None):
    if host.startswith("id."):
        if ID_PATHS.match(path) or path == "/":
            return resolve.resolve(path[1:], accept)
        if path.startswith("/kit/") and config.KIT_DIR:
            return static(Path(config.KIT_DIR).parent, path)
        return resolve.not_found(path[1:])
    # labs (and local tests: one server for both)
    if path in ("/search", "/api", "/dashboard", "/map", "/sparql"):
        return Response(301, "", "text/plain", {"Location": path + "/"})
    if path == "/search/":
        return Response(200, search.view(qs))
    if path == "/api/search":
        return api.j(search.api(qs))
    if path == "/api/lookup":
        return api.lookup(qs)
    if path == "/api/resolve":
        return api.resolve(qs)
    if path.startswith("/api/entity/"):
        return api.entity(path.rsplit("/", 1)[1])
    if path in ("/reconcile", "/reconcile/"):
        return api.reconcile(qs, body)
    if path == "/reconcile/suggest/entity":
        return api.suggest(qs)
    if path == "/reconcile/preview":
        return api.preview(qs)
    m = re.fullmatch(r"/feeds/(?:(series|field)/([^/]+)|upcoming)\.ics", path)
    if m:
        return api.feed(m.group(1) or "all", m.group(2))
    if path == "/dashboard/":
        return Response(200, dashboard.view())
    if path == "/status.json":
        return api.j(dashboard.status())
    if ID_PATHS.match(path):
        return resolve.resolve(path[1:], accept)
    if path.startswith("/generated/"):
        return static(config.GENERATED, path.replace("/generated/", "/", 1))
    if path.startswith("/kit/") and config.KIT_DIR:
        return static(Path(config.KIT_DIR).parent, path)
    if SITE:
        return static(Path(SITE), path, index=True)
    return error_page(404, "Not found", "Nothing here.")


def static(root, path, index=False):
    """A file below root (local tests; nginx serves these in production)."""
    f = (root / path.lstrip("/")).resolve()
    if index and f.is_dir():
        f = f / "index.html"
    if not f.is_file() or root.resolve() not in f.parents:
        return error_page(404, "Not found", "Nothing here.")
    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    data = f.read_bytes()
    if f.suffix == ".html":
        from common import kit
        data = kit(data.decode("utf-8")).encode("utf-8")
    return Response(200, data, ctype)


def main():
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    server.daemon_threads = True
    signal.signal(signal.SIGTERM, lambda *a: os._exit(0))   # serve_forever runs in this thread: no shutdown()
    print(f"confref labs on {config.HOST}:{config.PORT}, index {config.DB}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
