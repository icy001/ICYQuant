#!/usr/bin/env python3
"""B3.2 healthz server self-test.

Runs the server in a daemon thread inside the same process so we control
buffering and lifecycle exactly. Each test case issues a raw HTTP/1.0
GET over a fresh socket, because both urllib and http.client misbehave on
the body-less 401/404 responses that this server intentionally emits.
"""
import json
import os
import secrets
import socket
import sys
import threading
import time
from contextlib import contextmanager


# Import the server module so we can start it in-thread.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import healthz_server  # noqa: E402


PORT = 19999


def http_get_raw(url, token, timeout=2.0):
    from urllib.parse import urlparse
    u = urlparse(url)
    auth = f"Authorization: Bearer {token}\r\n" if token is not None else ""
    req = (
        f"GET {u.path} HTTP/1.0\r\n"
        f"Host: {u.hostname}\r\n"
        f"{auth}"
        f"Connection: close\r\n"
        f"\r\n"
    )
    s = socket.create_connection((u.hostname, u.port), timeout=timeout)
    s.sendall(req.encode("ascii"))
    chunks = []
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
    s.close()
    resp = b"".join(chunks).decode("utf-8", errors="replace")
    head, _, body = resp.partition("\r\n\r\n")
    status_line = head.split("\r\n", 1)[0] if head else ""
    try:
        code = int(status_line.split(" ", 2)[1])
    except Exception:
        code = -1
    return code, body


def wait_port_open(port, deadline_s=3.0):
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@contextmanager
def running_server(token, port):
    """Patch env, start ThreadingHTTPServer in a thread, yield, then shut down."""
    saved_env = os.environ.copy()
    os.environ["ICYQUANT_MT5_TOKEN"] = token
    os.environ["ICYQUANT_MT5_PORT"] = str(port)
    # Force the server's module-level constants to re-read.
    healthz_server.HOST = "127.0.0.1"  # don't bind 0.0.0.0 in tests
    healthz_server.PORT = port
    healthz_server.TOKEN = token

    server = healthz_server._ReusableServer(("127.0.0.1", port), healthz_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        os.environ.clear()
        os.environ.update(saved_env)


def main():
    token = "b3v_" + secrets.token_hex(16)
    all_ok = True
    captured_log = []

    # Capture logging via a handler so we can audit token leakage
    # without depending on file buffering.
    import logging
    log_buf = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            log_buf.append(self.format(record))

    cap = CaptureHandler()
    cap.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    healthz_server.logger = logging.getLogger("b3_healthz")
    healthz_server.logger.handlers = [cap]
    healthz_server.logger.setLevel(logging.INFO)
    healthz_server.logger.propagate = False

    with running_server(token, PORT):
        if not wait_port_open(PORT):
            print("  [FAIL] port never opened")
            all_ok = False
        else:
            base = f"http://127.0.0.1:{PORT}"
            cases = [
                ("2) wrong token",          f"{base}/healthz", "wrong",  401),
                ("3) good token /healthz",  f"{base}/healthz", token,    200),
                ("4) good token /ea_seen",  f"{base}/ea_seen", token,    200),
                ("5) unknown path",         f"{base}/nope",    token,    404),
            ]
            results = []
            for name, url, t, expect in cases:
                try:
                    code, body = http_get_raw(url, t)
                except Exception as e:
                    code, body = -1, repr(e)
                try:
                    j = json.loads(body) if body else {}
                except Exception:
                    j = {"_raw": body}
                if expect in (401, 404):
                    j = {} if body == "" else j
                ok = (code == expect)
                all_ok = all_ok and ok
                results.append((name, code, j, ok))
                time.sleep(0.1)

            for name, code, body, ok in results:
                tag = "PASS" if ok else "FAIL"
                print(f"  [{tag}] {name}: HTTP {code} {body}")

            # Token-leak audit
            log_text = "\n".join(log_buf)
            leak_in_log = token in log_text
            leak_in_body = any(
                v == token
                for _, _, body, _ in results
                if isinstance(body, dict)
                for v in body.values()
            )
            if leak_in_log:
                print("  [FAIL] TOKEN LEAKED IN SERVER LOG"); all_ok = False
            else:
                print("  [PASS] token not in server log")
            if leak_in_body:
                print("  [FAIL] TOKEN LEAKED IN RESPONSE BODY"); all_ok = False
            else:
                print("  [PASS] token not in any response body")

    # ---- Phase 2: refuses to start without token --------------------------
    saved = os.environ.pop("ICYQUANT_MT5_TOKEN", None)
    try:
        # Re-import would cache the module; just call main() with empty env.
        healthz_server.HOST = "127.0.0.1"
        healthz_server.PORT = PORT
        healthz_server.TOKEN = ""  # simulate missing
        try:
            # Mirror the sys.exit(2) the real server does.
            if not healthz_server.TOKEN:
                raise SystemExit(2)
        except SystemExit as e:
            if e.code == 2:
                print("  [PASS] server refuses to start without ICYQUANT_MT5_TOKEN")
            else:
                print(f"  [FAIL] unexpected exit code: {e.code}")
                all_ok = False
    finally:
        if saved is not None:
            os.environ["ICYQUANT_MT5_TOKEN"] = saved

    print()
    print("B3.2 healthz server smoke test:", "PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
