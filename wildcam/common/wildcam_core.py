"""Shared server for the NERDS uc wild cam loggers.

Both apps (Land & Air Cam, Sea Cam) use this module and differ only in their AppConfig:
page title, accent colour and the PostgreSQL table their observations live in.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import socket
import ssl
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import psycopg
from psycopg import sql

# "" or "/segment[/segment...]" without a trailing slash, e.g. "/sea" or "/cams/sea".
_BASE_PATH_RE = re.compile(r"(/[A-Za-z0-9._~-]+)*")


@dataclass(frozen=True)
class AppConfig:
    title: str
    table: str
    accent: str = "#333333"
    animal_hint: str = ""


class MemoryStore:
    """Fallback when no DATABASE_URL is set. Local development only, data is lost on restart."""

    def __init__(self) -> None:
        self._items: list[dict[str, str]] = []

    def add(self, entry: dict[str, str]) -> None:
        self._items.append(entry)

    def list(self) -> list[dict[str, str]]:
        return list(self._items)


class PostgresStore:
    """Stores observations in the central PostgreSQL server shared by all worker nodes.

    Each app gets its own table, so land/air and sea observations never mix.
    """

    def __init__(self, url: str, table: str) -> None:
        self._url = url
        self._table = sql.Identifier(table)
        self._init_schema()

    def _init_schema(self) -> None:
        schema = sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {} (
                id SERIAL PRIMARY KEY,
                animal TEXT NOT NULL,
                stream TEXT NOT NULL,
                visible_at TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ).format(self._table)
        # The DB VM may still be booting when a worker starts, so retry for about a minute.
        for attempt in range(1, 31):
            try:
                with psycopg.connect(self._url) as conn:
                    conn.execute(schema)
                return
            except psycopg.OperationalError as exc:
                print(f"Database not reachable (attempt {attempt}/30): {exc}", flush=True)
                time.sleep(2)
        raise SystemExit("Giving up: could not connect to the database")

    def add(self, entry: dict[str, str]) -> None:
        query = sql.SQL("INSERT INTO {} (animal, stream, visible_at) VALUES (%s, %s, %s)").format(
            self._table
        )
        with psycopg.connect(self._url) as conn:
            conn.execute(query, (entry["animal"], entry["stream"], entry["visible_at"]))

    def list(self) -> list[dict[str, str]]:
        query = sql.SQL("SELECT animal, stream, visible_at FROM {} ORDER BY id").format(self._table)
        with psycopg.connect(self._url) as conn:
            rows = conn.execute(query).fetchall()
        return [{"animal": a, "stream": s, "visible_at": v} for a, s, v in rows]


def normalize_base_path(value: str | None) -> str:
    """Turn "sea", "/sea" or "/sea/" into "/sea"; "" or "/" into "". Reject anything else."""
    path = (value or "").strip().strip("/")
    path = f"/{path}" if path else ""
    if not _BASE_PATH_RE.fullmatch(path):
        raise SystemExit(f"Invalid BASE_PATH {value!r}: use something like /sea")
    return path


def format_visible_at(visible_at: str) -> str:
    try:
        return datetime.fromisoformat(visible_at).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return visible_at


def parse_observation(body: str) -> dict[str, str] | None:
    payload = parse_qs(body, keep_blank_values=True)
    animal = payload.get("animal", [""])[0].strip()
    stream = payload.get("stream", [""])[0].strip()
    visible_at = payload.get("visibleAt", [""])[0].strip()
    if not animal or not stream or not visible_at:
        return None
    return {
        "animal": animal,
        "stream": stream,
        "visible_at": format_visible_at(visible_at),
    }


def render_page(
    config: AppConfig,
    current_observations: list[dict[str, str]],
    base_path: str = "",
    served_by: str = "",
) -> bytes:
    rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(item['animal'])}</td>"
            f"<td>{html.escape(item['visible_at'])}</td>"
            f"<td>{html.escape(item['stream'])}</td>"
            "</tr>"
        )
        for item in current_observations
    )
    title = html.escape(config.title)
    accent = html.escape(config.accent)
    hint = html.escape(config.animal_hint)
    action = html.escape(f"{base_path}/observations")
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NERDS uc {title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; max-width: 900px; }}
    h1 {{ color: {accent}; border-bottom: 4px solid {accent}; padding-bottom: 0.5rem; }}
    form {{ display: grid; gap: 0.75rem; max-width: 450px; margin-bottom: 1.5rem; }}
    label {{ font-weight: 600; }}
    input, button {{ padding: 0.5rem; font-size: 1rem; }}
    button {{ background: {accent}; color: #fff; border: none; cursor: pointer; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
    footer {{ margin-top: 1.5rem; color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <form method="post" action="{action}">
    <div>
      <label for="animal">Animal</label><br>
      <input id="animal" name="animal" type="text" placeholder="{hint}" required>
    </div>
    <div>
      <label for="stream">Stream</label><br>
      <input id="stream" name="stream" type="text" required>
    </div>
    <div>
      <label for="visibleAt">Visible at</label><br>
      <input id="visibleAt" name="visibleAt" type="datetime-local" required>
    </div>
    <button type="submit">Add observation</button>
  </form>
  <h2>Logged Observations</h2>
  <table>
    <thead>
      <tr>
        <th>Animal</th>
        <th>Visible At</th>
        <th>Stream</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <footer>Served by: {html.escape(served_by)}</footer>
</body>
</html>"""
    return html_page.encode("utf-8")


class ObservationHandler(BaseHTTPRequestHandler):
    # Filled in by build_server() on a per-server subclass.
    config: AppConfig
    store: MemoryStore | PostgresStore
    base_path: str = ""

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/health", f"{self.base_path}/health"):
            self._send_text("ok")
            return
        if self.base_path and path == self.base_path:
            # "/sea" -> "/sea/" so the browser has a stable base URL.
            self._redirect(f"{self.base_path}/", HTTPStatus.MOVED_PERMANENTLY)
            return
        if path != f"{self.base_path}/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = render_page(
            self.config, self.store.list(), self.base_path, served_by=socket.gethostname()
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != f"{self.base_path}/observations":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        entry = parse_observation(body)
        if entry is not None:
            self.store.add(entry)
        self._redirect(f"{self.base_path}/", HTTPStatus.SEE_OTHER)

    def _redirect(self, location: str, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_text(self, text: str) -> None:
        content = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        return


def build_server(
    config: AppConfig,
    host: str,
    port: int,
    store: MemoryStore | PostgresStore,
    base_path: str = "",
    certfile: str | None = None,
    keyfile: str | None = None,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredObservationHandler",
        (ObservationHandler,),
        {"config": config, "store": store, "base_path": base_path},
    )
    server = ThreadingHTTPServer((host, port), handler)
    if certfile and keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def parse_args(config: AppConfig) -> argparse.Namespace:
    # Every option can also be given as an environment variable, which is what Docker uses.
    parser = argparse.ArgumentParser(description=f"NERDS uc {config.title}")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8080")), type=int)
    parser.add_argument("--base-path", default=os.environ.get("BASE_PATH", ""))
    parser.add_argument("--certfile", default=os.environ.get("TLS_CERTFILE"))
    parser.add_argument("--keyfile", default=os.environ.get("TLS_KEYFILE"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    return parser.parse_args()


def run(config: AppConfig) -> None:
    args = parse_args(config)
    base_path = normalize_base_path(args.base_path)
    if args.database_url:
        store: MemoryStore | PostgresStore = PostgresStore(args.database_url, config.table)
    else:
        print("WARNING: DATABASE_URL not set, observations are kept in memory only", flush=True)
        store = MemoryStore()
    server = build_server(
        config, args.host, args.port, store, base_path, args.certfile, args.keyfile
    )
    scheme = "https" if args.certfile and args.keyfile else "http"
    print(
        f"{config.title}: serving {scheme.upper()} on {scheme}://{args.host}:{args.port}{base_path}/",
        flush=True,
    )
    server.serve_forever()


def healthcheck() -> int:
    """Container HEALTHCHECK: 0 if this container's /health answers, 1 otherwise."""
    port = os.environ.get("PORT", "8080")
    use_tls = bool(os.environ.get("TLS_CERTFILE") and os.environ.get("TLS_KEYFILE"))
    scheme = "https" if use_tls else "http"
    # Checking our own loopback port; the certificate is issued for the public name.
    context = ssl._create_unverified_context() if use_tls else None
    url = f"{scheme}://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=2, context=context) as resp:
            return 0 if resp.status == 200 else 1
    except OSError:
        return 1
