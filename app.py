from __future__ import annotations

import argparse
import html
import os
import socket
import ssl
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import psycopg


class MemoryStore:
    """Fallback when no DATABASE_URL is set. Local development only, data is lost on restart."""

    def __init__(self) -> None:
        self._items: list[dict[str, str]] = []

    def add(self, entry: dict[str, str]) -> None:
        self._items.append(entry)

    def list(self) -> list[dict[str, str]]:
        return list(self._items)


class PostgresStore:
    """Stores observations in the central PostgreSQL server shared by all worker nodes."""

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS observations (
            id SERIAL PRIMARY KEY,
            animal TEXT NOT NULL,
            stream TEXT NOT NULL,
            visible_at TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._init_schema()

    def _init_schema(self) -> None:
        # The DB VM may still be booting when a worker starts, so retry for about a minute.
        for attempt in range(1, 31):
            try:
                with psycopg.connect(self._url) as conn:
                    conn.execute(self.SCHEMA)
                return
            except psycopg.OperationalError as exc:
                print(f"Database not reachable (attempt {attempt}/30): {exc}", flush=True)
                time.sleep(2)
        raise SystemExit("Giving up: could not connect to the database")

    def add(self, entry: dict[str, str]) -> None:
        with psycopg.connect(self._url) as conn:
            conn.execute(
                "INSERT INTO observations (animal, stream, visible_at) VALUES (%s, %s, %s)",
                (entry["animal"], entry["stream"], entry["visible_at"]),
            )

    def list(self) -> list[dict[str, str]]:
        with psycopg.connect(self._url) as conn:
            rows = conn.execute(
                "SELECT animal, stream, visible_at FROM observations ORDER BY id"
            ).fetchall()
        return [{"animal": a, "stream": s, "visible_at": v} for a, s, v in rows]


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


def render_page(current_observations: list[dict[str, str]], served_by: str = "") -> bytes:
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
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NERDS uc Wild Cam Log</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; max-width: 900px; }}
    form {{ display: grid; gap: 0.75rem; max-width: 450px; margin-bottom: 1.5rem; }}
    label {{ font-weight: 600; }}
    input, button {{ padding: 0.5rem; font-size: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
    footer {{ margin-top: 1.5rem; color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Wild Cam Observation Log</h1>
  <form method="post" action="/observations">
    <div>
      <label for="animal">Animal</label><br>
      <input id="animal" name="animal" type="text" required>
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
    store: MemoryStore | PostgresStore = MemoryStore()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_text("ok")
            return
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = render_page(self.store.list(), served_by=socket.gethostname())
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if self.path != "/observations":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        entry = parse_observation(body)
        if entry is not None:
            self.store.add(entry)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
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
    host: str,
    port: int,
    store: MemoryStore | PostgresStore,
    certfile: str | None = None,
    keyfile: str | None = None,
) -> ThreadingHTTPServer:
    ObservationHandler.store = store
    server = ThreadingHTTPServer((host, port), ObservationHandler)
    if certfile and keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def parse_args() -> argparse.Namespace:
    # Every option can also be given as an environment variable, which is what Docker uses.
    parser = argparse.ArgumentParser(description="NERDS uc Wild Cam logger")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8080")), type=int)
    parser.add_argument("--certfile", default=os.environ.get("TLS_CERTFILE"))
    parser.add_argument("--keyfile", default=os.environ.get("TLS_KEYFILE"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.database_url:
        store: MemoryStore | PostgresStore = PostgresStore(args.database_url)
    else:
        print("WARNING: DATABASE_URL not set, observations are kept in memory only", flush=True)
        store = MemoryStore()
    server = build_server(args.host, args.port, store, args.certfile, args.keyfile)
    scheme = "https" if args.certfile and args.keyfile else "http"
    print(f"Serving {scheme.upper()} on {scheme}://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
