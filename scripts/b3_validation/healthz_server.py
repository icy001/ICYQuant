#!/usr/bin/env python3
"""B3.2 read-only /healthz server.

Stand-in for the future services/integrations/mt5_bridge/server.py.
- stdlib only (no FastAPI / uvicorn), so no install step is needed.
- Bearer token from $ICYQUANT_MT5_TOKEN (NEVER printed, NEVER logged).
- Logs only the request line + status, never the header value.

Endpoints
    GET /healthz   → 200 {"status":"ok","ea_seen":<bool>,"last_seen":<ts>}
    GET /ea_seen   → 200 {"ea_seen":<bool>,"last_seen":<ts>}    (read-only probe)
    *              → 404
"""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = os.environ.get("ICYQUANT_MT5_HOST", "0.0.0.0")
PORT = int(os.environ.get("ICYQUANT_MT5_PORT", "9100"))
TOKEN = os.environ.get("ICYQUANT_MT5_TOKEN", "")

if not TOKEN:
    print(
        "[FATAL] ICYQUANT_MT5_TOKEN env var is required. Refusing to start.",
        file=sys.stderr,
    )
    sys.exit(2)


# Module-level logger so tests can attach a capture handler without
# fighting global logging.basicConfig side-effects.
logger = logging.getLogger("b3_healthz")

# Last time the EA successfully authenticated to any endpoint.
_LAST_SEEN: float | None = None


def _now() -> float:
    return time.time()


def _require_token(handler: BaseHTTPRequestHandler) -> bool:
    auth = handler.headers.get("Authorization", "")
    return auth == f"Bearer {TOKEN}"


def _no_body(handler, status: int) -> None:
    """Error responses carry no body.

    BaseHTTPRequestHandler closes the connection after 401/404 under
    HTTP/1.0 by default, which makes any body write raise
    ``IncompleteRead`` on stdlib clients. A 0-length body is the
    standard, interoperable shape.
    """
    handler.send_response(status)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _json(handler: BaseHTTPRequestHandler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class _ReusableServer(HTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    # Default HTTP/1.0 is the most interoperable choice here: each request
    # is its own short-lived connection, no keep-alive state to corrupt
    # across cases, and clients (curl, urllib, http.client, MQL5
    # WebRequest) all handle it cleanly.
    protocol_version = "HTTP/1.0"

    # Quiet the default per-request stderr; route through our logger instead.
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.info("%s - - %s", self.address_string(), format % args)

    def do_GET(self) -> None:  # noqa: N802
        global _LAST_SEEN
        path = urlparse(self.path).path

        if path not in ("/healthz", "/ea_seen"):
            _no_body(self, 404)
            return

        if not _require_token(self):
            logger.warning("auth failure from %s on %s", self.address_string(), path)
            _no_body(self, 401)
            return

        _LAST_SEEN = _now()
        ea_seen = _LAST_SEEN is not None
        body = {
            "status": "ok" if path == "/healthz" else "probe",
            "ea_seen": ea_seen,
            "last_seen": _LAST_SEEN,
        }
        _json(self, 200, body)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = _ReusableServer((HOST, PORT), Handler)
    logger.info("B3.2 healthz listening on http://%s:%d", HOST, PORT)
    logger.info("token configured: yes (length=%d, value redacted)", len(TOKEN))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
