"""Opt-in loopback phone gateway. A private HTTPS proxy can expose one origin."""

import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

from .model import UserError
from .service import completed_file, dispatch

ASSETS = Path(__file__).with_name("phone_ui")
COOKIE = "lw_session"
MAX_BODY = 8 * 1024
SESSION_AGE = 12 * 3600
JOB_FIELDS = ("id", "title", "artist", "state", "desired", "progress", "bytes", "total", "error", "format")
ROUTES = {"/": ("index.html", "text/html; charset=utf-8"),
          "/phone.js": ("phone.js", "text/javascript; charset=utf-8"),
          "/phone.css": ("phone.css", "text/css; charset=utf-8")}


def checked_origin(value, port):
    if not value:
        return f"http://127.0.0.1:{port}"
    url = urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username is not None
            or url.password is not None or url.path not in ("", "/") or url.query or url.fragment
            or not re.fullmatch(r"[a-zA-Z0-9.\-]+(?::[0-9]{1,5})?", url.netloc)):
        raise ValueError("Use the HTTPS origin of your private proxy, including its port if needed.")
    _ = url.port  # Reject ports outside the valid range.
    return f"https://{url.netloc.lower()}"


class Pairing:
    def __init__(self):
        # 80 bits in groups that can be typed on a second device.
        raw = secrets.token_hex(10)
        self.display_code = "-".join(raw[i:i+4] for i in range(0, len(raw), 4))
        self.deadline = time.monotonic() + 600
        self.session = None
        self.expires = 0.0
        self.lock = threading.Lock()

    def redeem(self, code):
        if not isinstance(code, str) or not code.isascii():
            return None
        with self.lock:
            if (not self.display_code or time.monotonic() >= self.deadline
                    or not hmac.compare_digest(code.strip().lower().replace("-", ""), self.display_code.replace("-", ""))):
                return None
            self.display_code = None
            self.session = secrets.token_urlsafe(32)
            self.expires = time.monotonic() + SESSION_AGE
            return self.session

    def allowed(self, token):
        with self.lock:
            return bool(self.session and token and token.isascii() and time.monotonic() < self.expires
                        and hmac.compare_digest(self.session, token))


class PhoneServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, store, origin=None, port=8765):
        self.store = store
        self.pairing = Pairing()
        self.slots = threading.BoundedSemaphore(12)
        super().__init__(("127.0.0.1", port), PhoneRequest)
        try:
            self.origin = checked_origin(origin, self.server_port)
        except ValueError:
            self.server_close()
            raise
        self.hosts = {urlsplit(self.origin).netloc, f"127.0.0.1:{self.server_port}"}

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            request.settimeout(30)
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def byte_range(header, size):
    if not header:
        return 0, size - 1
    match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", header)
    if not match or not any(match.groups()):
        raise ValueError()
    left, right = match.groups()
    if left:
        start, end = int(left), min(int(right), size - 1) if right else size - 1
    else:
        start, end = max(0, size - int(right)), size - 1
    if start > end or start >= size:
        raise ValueError()
    return start, end


class PhoneRequest(BaseHTTPRequestHandler):
    server_version = "Longwave"
    sys_version = ""

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

    def authorized(self):
        try:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            value = jar.get(COOKIE)
            return self.server.pairing.allowed(value.value if value else None)
        except CookieError:
            return False

    def body(self, status, data, kind="application/json; charset=utf-8", cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            secure = "; Secure" if self.server.origin.startswith("https:") else ""
            self.send_header("Set-Cookie", f"{COOKIE}={cookie}; Max-Age={SESSION_AGE}; HttpOnly; Path=/; SameSite=Strict{secure}")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def respond(self, status, value, cookie=None):
        self.body(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), cookie=cookie)

    def valid_host(self):
        if self.headers.get("Host", "").lower() in self.server.hosts:
            return True
        self.respond(403, {"error": "Use the address printed by Longwave."})
        return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.valid_host():
            return
        if self.path in ROUTES:
            name, kind = ROUTES[self.path]
            self.body(200, (ASSETS / name).read_bytes(), kind)
            return
        if not self.authorized():
            self.respond(401, {"error": "Enter the pairing code from your computer."})
            return
        if self.path == "/api/jobs":
            state = dispatch(self.server.store, {"version": 1, "command": "snapshot"})
            self.respond(200, {"jobs": [{key:j.get(key) for key in JOB_FIELDS} for j in state["jobs"]]})
            return
        audio = re.fullmatch(r"/audio/([a-f0-9-]{36})/(listen|save)", self.path)
        if audio:
            try:
                path = completed_file(self.server.store, audio.group(1))
                self.send_audio(path, audio.group(2) == "save")
            except (FileNotFoundError, UserError):
                self.respond(404, {"error": "This file is unavailable."})
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # The player sought elsewhere or the user stopped the transfer.
            return
        self.respond(404, {"error": "Unknown resource."})

    def send_audio(self, path, download):
        with path.open("rb") as source:
            size = os.fstat(source.fileno()).st_size
            requested = self.headers.get("Range")
            try:
                start, end = byte_range(requested, size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            remaining = end - start + 1
            self.send_response(206 if requested else 200)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            disposition = "attachment" if download else "inline"
            # Older mobile download managers only parse the ASCII filename parameter.
            suffix = re.sub(r"[^a-zA-Z0-9.]", "", path.suffix)
            basename = re.sub(r"[^a-zA-Z0-9 _.-]", "_", path.stem).strip(" ._") or "Longwave"
            self.send_header("Content-Disposition",
                             f"{disposition}; filename=\"{basename}{suffix}\"; filename*=UTF-8''{quote(path.name, safe='')}")
            self.send_header("Content-Length", str(remaining))
            if requested:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            source.seek(start)
            while remaining:
                chunk = source.read(min(remaining, 128 * 1024))
                if not chunk:
                    return
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        if not self.valid_host():
            return
        if self.headers.get("Origin") != self.server.origin:
            self.respond(403, {"error": "Open the paired Longwave page to make changes."})
            return
        if self.path not in ("/api/pair", "/api/jobs") or self.headers.get_content_type() != "application/json":
            self.respond(400, {"error": "Unknown request."})
            return
        if self.path == "/api/jobs" and not self.authorized():
            self.respond(401, {"error": "Pair this device first."})
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if size < 1 or size > MAX_BODY:
                raise ValueError()
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError()
            if self.path == "/api/pair":
                session = self.server.pairing.redeem(payload.get("code"))
                if not session:
                    self.respond(403, {"error": "This code is incorrect, expired or already used."})
                else:
                    self.respond(200, {"paired": True}, cookie=session)
                return
            if payload.get("command") not in ("create", "pause", "resume", "cancel"):
                raise ValueError()
            job = dispatch(self.server.store, {**payload, "version": 1})
            self.respond(200, {"id": job["id"], "state": job["state"]})
        except UserError as exc:
            self.respond(400, {"error": str(exc)})
        except (ValueError, TypeError):
            self.respond(400, {"error": "Check the request and try again."})


def serve(store, origin=None, port=8765):
    from .runtime import require_tools
    require_tools(store)
    with PhoneServer(store, origin, port) as server:
        print(f"Open {server.origin}\nPairing code (one use, ten minutes): {server.pairing.display_code}\n"
              "Pair only your own device. It will have access to your queue and saved tracks. Press Ctrl+C to disconnect.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
