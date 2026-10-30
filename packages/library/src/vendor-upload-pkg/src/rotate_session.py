#!/usr/bin/env python3
"""Rotate __session in cookie.txt by calling Clerk's token endpoint.

Clerk session JWTs live only ~5 min. The browser auto-rotates them via
clerk.publish.example.com/v1/client/sessions/{sid}/tokens (called with the
long-lived __client cookie). This script does the same from the CLI so
upload.py doesn't have to ask a human every 5 minutes.

Usage (standalone):
    python3 rotate_session.py [--cookie-file PATH] [-v]

Or import: rotate_session.rotate(Path("cookie.txt")) → True on success.

On macOS the default LibreSSL handshake to clerk.publish.example.com fails
intermittently against some Cloudflare edge IPs (SSL_ERROR_SYSCALL).
We resolve candidate IPs and retry across them.
"""

from __future__ import annotations

import argparse
import base64
import json
import socket
import ssl
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import connection as urllib3_connection

CLERK_HOST = "clerk.publish.example.com"
ORIGIN = "https://www.publish.example.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
CLERK_JS_VERSION = "5.0.0"
ATTEMPTS_PER_IP = 2
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 15


def _b64url_decode(seg: str) -> bytes:
    seg += "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg)


def _jwt_payload(jwt: str) -> dict:
    parts = jwt.split(".")
    if len(parts) < 2:
        raise ValueError("malformed JWT")
    return json.loads(_b64url_decode(parts[1]))


def _read_cookies(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip().upper()] = v.strip().strip('"').strip("'")
    return out


def _write_session(path: Path, new_session: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    replaced = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k = stripped.split("=", 1)[0].strip().upper()
        if k in ("SESSION", "__SESSION"):
            lines[i] = f"SESSION={new_session}"
            replaced = True
            break
    if not replaced:
        lines.append(f"SESSION={new_session}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    ips: list[str] = []
    for fam, *_rest, sockaddr in infos:
        if fam != socket.AF_INET:
            continue
        ip = sockaddr[0]
        if ip not in ips:
            ips.append(ip)
    return ips


class _PinnedIPAdapter(HTTPAdapter):
    """Forces every connection from this adapter to a single IP."""

    def __init__(self, ip: str, *args, **kwargs):
        self._pinned_ip = ip
        super().__init__(*args, **kwargs)

    def get_connection(self, url, proxies=None):  # type: ignore[override]
        return super().get_connection(url, proxies)

    def init_poolmanager(self, *args, **kwargs):
        original = urllib3_connection.create_connection

        pinned_ip = self._pinned_ip

        def patched(address, *a, **kw):
            host, port = address
            return original((pinned_ip, port), *a, **kw)

        # Patch at module level for this poolmanager's connections. Safe
        # because we only use this adapter for the rotation request.
        urllib3_connection.create_connection = patched
        try:
            return super().init_poolmanager(*args, **kwargs)
        finally:
            urllib3_connection.create_connection = original


def _attempt_rotation(sid: str, client_jwt: str, client_uat: str | None, ip: str) -> str | None:
    url = f"https://{CLERK_HOST}/v1/client/sessions/{sid}/tokens?_clerk_js_version={CLERK_JS_VERSION}"
    cookie_parts = [f"__client={client_jwt}"]
    if client_uat:
        cookie_parts.append(f"__client_uat={client_uat}")
    headers = {
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Cookie": "; ".join(cookie_parts),
    }
    sess = requests.Session()
    sess.trust_env = False
    sess.mount(f"https://{CLERK_HOST}", _PinnedIPAdapter(ip))
    try:
        r = sess.post(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, ssl.SSLError, OSError):
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    jwt = data.get("jwt") or (data.get("response") or {}).get("jwt")
    if not jwt or not isinstance(jwt, str) or jwt.count(".") < 2:
        return None
    return jwt


def rotate(cookie_file: Path, verbose: bool = False) -> bool:
    """Rotate __session in cookie_file in-place. Returns True on success."""

    def log(msg: str) -> None:
        if verbose:
            print(f"[rotate] {msg}", file=sys.stderr)

    cookies = _read_cookies(cookie_file)
    session = cookies.get("SESSION") or cookies.get("__SESSION")
    client = cookies.get("CLIENT") or cookies.get("__CLIENT")
    client_uat = cookies.get("CLIENT_UAT") or cookies.get("__CLIENT_UAT")
    if not session:
        log("no SESSION= in cookie file — cannot extract sid")
        return False
    if not client:
        log("no CLIENT= in cookie file — cannot authenticate to Clerk")
        return False

    try:
        payload = _jwt_payload(session)
    except Exception as e:
        log(f"failed to decode SESSION JWT: {e}")
        return False
    sid = payload.get("sid")
    if not sid:
        log("SESSION JWT has no sid")
        return False

    ips = _resolve_ips(CLERK_HOST)
    if not ips:
        log(f"failed to resolve {CLERK_HOST}")
        return False
    log(f"sid={sid}  candidate IPs: {ips}")

    for ip in ips:
        for attempt in range(1, ATTEMPTS_PER_IP + 1):
            log(f"POST via {ip} (attempt {attempt}/{ATTEMPTS_PER_IP})")
            jwt = _attempt_rotation(sid, client, client_uat, ip)
            if jwt:
                _write_session(cookie_file, jwt)
                try:
                    new_payload = _jwt_payload(jwt)
                    log(f"OK — new exp={new_payload.get('exp')}")
                except Exception:
                    pass
                return True
            time.sleep(0.5)
    log("all rotation attempts failed")
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cookie-file",
        default=str(Path(__file__).resolve().parent / "cookie.txt"),
        help="path to cookie.txt (default: alongside this script)",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    ok = rotate(Path(args.cookie_file).expanduser(), verbose=args.verbose)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
