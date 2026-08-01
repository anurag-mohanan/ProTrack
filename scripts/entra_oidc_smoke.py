"""Entra / OIDC smoke checks for R10.

Usage:
  python scripts/entra_oidc_smoke.py
  python scripts/entra_oidc_smoke.py --testing
  python scripts/entra_oidc_smoke.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _ok(msg: str) -> None:
    print(f"OK   {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL {msg}")


def _warn(msg: str) -> None:
    print(f"WARN {msg}")


def run_inprocess(*, testing: bool) -> int:
    """Validate config helpers + /auth/oidc/status via TestClient."""
    if testing:
        os.environ["OIDC_ENABLED"] = "true"
        os.environ["OIDC_TESTING"] = "true"

    from fastapi.testclient import TestClient

    from app.core import oidc
    from app.main import app

    failures = 0
    print("=== Entra / OIDC smoke (in-process) ===\n")

    enabled = oidc.oidc_enabled()
    configured = oidc.oidc_configured()
    available = oidc.oidc_available()
    print(f"OIDC_ENABLED={enabled} configured={configured} available={available}")

    if testing:
        if not available:
            _fail("OIDC_TESTING path should be available when OIDC_ENABLED=true")
            failures += 1
        else:
            _ok("Testing mode available")
        url = oidc.build_authorize_url(state="smoke-state", nonce="smoke-nonce")
        if "testing-authorize" not in url:
            _fail(f"Unexpected testing authorize URL: {url}")
            failures += 1
        else:
            _ok(f"Authorize URL (testing): {url}")
    else:
        settings = oidc.oidc_settings()
        if not enabled:
            _warn("OIDC_ENABLED is false — enable for real Entra smoke")
        if settings is None:
            _warn("OIDC_* credentials incomplete — discovery skipped")
        else:
            _ok(f"Issuer configured: {settings.issuer}")
            try:
                discovery = oidc._discover(settings)
                for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                    if key not in discovery:
                        _fail(f"Discovery missing {key}")
                        failures += 1
                    else:
                        _ok(f"Discovery {key}")
            except Exception as exc:
                _fail(f"Discovery request failed: {exc}")
                failures += 1

    client = TestClient(app)
    status = client.get("/api/v1/auth/oidc/status")
    if status.status_code != 200:
        _fail(f"/auth/oidc/status HTTP {status.status_code}")
        failures += 1
    else:
        body = status.json()
        _ok(f"/auth/oidc/status -> {body}")

    if testing and available:
        login = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
        # May be 302 to testing-authorize or 200 JSON depending on route shape
        if login.status_code not in (200, 302, 307):
            _fail(f"/auth/oidc/login HTTP {login.status_code}: {login.text[:200]}")
            failures += 1
        else:
            _ok(f"/auth/oidc/login HTTP {login.status_code}")

    print()
    if failures:
        print(f"RESULT: {failures} failure(s). See docs/R10_ENTRA_SSO_SMOKE.md for manual steps.")
        return 1
    print("RESULT: dry-run passed. Complete manual Entra browser table in R10_ENTRA_SSO_SMOKE.md.")
    return 0


def run_remote(base_url: str) -> int:
    import httpx

    failures = 0
    print(f"=== Entra / OIDC smoke (remote {base_url}) ===\n")
    url = base_url.rstrip("/") + "/api/v1/auth/oidc/status"
    try:
        response = httpx.get(url, timeout=15.0)
    except Exception as exc:
        _fail(f"GET {url}: {exc}")
        return 1
    if response.status_code != 200:
        _fail(f"HTTP {response.status_code}: {response.text[:200]}")
        failures += 1
    else:
        _ok(f"status -> {response.json()}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="R10 Entra OIDC smoke")
    parser.add_argument("--testing", action="store_true", help="Force OIDC_TESTING path")
    parser.add_argument(
        "--base-url",
        default="",
        help="If set, only hit remote /auth/oidc/status (live API)",
    )
    args = parser.parse_args()
    if args.base_url:
        raise SystemExit(run_remote(args.base_url))
    raise SystemExit(run_inprocess(testing=args.testing))


if __name__ == "__main__":
    main()
