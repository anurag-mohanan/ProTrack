"""Run a lightweight API health audit and print a summary report."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

from fastapi.routing import APIRoute

from app.main import app
from tests.conftest import TestClient, login


@dataclass
class AuditResult:
    working: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _collect_get_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if "GET" not in route.methods:
            continue
        path = route.path
        if "{" in path:
            continue
        if path in {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}:
            continue
        routes.append((path, route.name or path))
    return sorted(routes, key=lambda item: item[0])


def run_audit() -> AuditResult:
    result = AuditResult()
    client = TestClient(app)
    token = login(client, "admin@protrack.local", "admin123")
    headers = {"Authorization": f"Bearer {token}"}

    for path, name in _collect_get_routes():
        response = client.get(path, headers=headers)
        if response.status_code == 200:
            try:
                response.json()
                result.working.append(path)
            except json.JSONDecodeError:
                result.warnings.append(f"{path} (non-JSON 200)")
        elif response.status_code in {401, 403, 404, 422}:
            result.warnings.append(f"{path} ({response.status_code})")
        else:
            result.failed.append(f"{path} ({response.status_code})")

    return result


def main() -> int:
    audit = run_audit()
    total = len(audit.working) + len(audit.warnings) + len(audit.failed)
    print("Application Health Report")
    print("=========================")
    print(f"APIs inspected: {total}")
    print(f"Passed: {len(audit.working)}")
    print(f"Warnings: {len(audit.warnings)}")
    print(f"Failed: {len(audit.failed)}")
    if audit.failed:
        print("\nFailed endpoints:")
        for item in audit.failed:
            print(f"  - {item}")
    if audit.warnings:
        print("\nWarnings:")
        for item in audit.warnings[:20]:
            print(f"  - {item}")
        if len(audit.warnings) > 20:
            print(f"  ... and {len(audit.warnings) - 20} more")
    return 1 if audit.failed else 0


if __name__ == "__main__":
    sys.exit(main())
