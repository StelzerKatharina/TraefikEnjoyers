from __future__ import annotations

import argparse
import html
import ssl
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


observations: list[dict[str, str]] = []


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


def render_page(current_observations: list[dict[str, str]]) -> bytes:
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
</body>
</html>"""
    return html_page.encode("utf-8")


class ObservationHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = render_page(observations)
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
            observations.append(entry)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def build_server(host: str, port: int, certfile: str, keyfile: str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), ObservationHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NERDS uc Wild Cam HTTPS logger")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8443, type=int)
    parser.add_argument("--certfile", default="cert.pem")
    parser.add_argument("--keyfile", default="key.pem")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = build_server(args.host, args.port, args.certfile, args.keyfile)
    print(f"Serving HTTPS on https://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
