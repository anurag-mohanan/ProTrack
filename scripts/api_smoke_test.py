"""Smoke-test major API endpoints against the live protrack.db."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.db.session import SessionLocal
from app.main import app


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def login(email: str = "admin@prosohm.com", password: str = "Password@123") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {response.status_code} {response.text}")
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def check(label: str, method: str, path: str, headers: dict, *, expect_list: bool = True) -> None:
    response = client.request(method, path, headers=headers)
    status = response.status_code
    if status != 200:
        print(f"FAIL {label}: HTTP {status} — {response.text[:200]}")
        return
    data = response.json()
    if expect_list:
        count = len(data) if isinstance(data, list) else "n/a"
        print(f"OK   {label}: HTTP 200, count={count}")
    else:
        print(f"OK   {label}: HTTP 200")


def main() -> None:
    headers = login()
    print("=== Authenticated API smoke test (live protrack.db) ===\n")

    check("Projects (lifecycle=all, limit=500)", "GET", "/api/v1/projects?lifecycle=all&limit=500", headers)
    check("Projects (default — expect all non-deleted)", "GET", "/api/v1/projects?limit=500", headers)
    check("Customers", "GET", "/api/v1/customers?limit=500", headers)
    check("Users", "GET", "/api/v1/users?limit=500", headers)
    check("Teams", "GET", "/api/v1/teams?limit=500", headers)
    check("Lookups teams", "GET", "/api/v1/lookups/teams", headers)
    check("Timesheets", "GET", "/api/v1/timesheets?limit=500", headers)
    check("Dashboard summary", "GET", "/api/v1/dashboard/summary", headers, expect_list=False)
    check("Dashboard KPIs", "GET", "/api/v1/dashboard/kpis", headers, expect_list=False)
    check("Reports project-hours", "GET", "/api/v1/reports/project-hours?include_archived=true", headers)
    check("Reports customer-summary", "GET", "/api/v1/reports/customer-summary?include_archived=true", headers)
    check("Lookups customers", "GET", "/api/v1/lookups/customers", headers)
    check("Lookups users", "GET", "/api/v1/lookups/users", headers)


if __name__ == "__main__":
    main()
