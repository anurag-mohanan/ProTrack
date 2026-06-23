"""Diagnose OpenAPI / Swagger generation issues."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    print("=== OpenAPI generation ===")
    schema = app.openapi()
    print(f"paths: {len(schema.get('paths', {}))}")
    print(f"schemas: {len(schema.get('components', {}).get('schemas', {}))}")
    print("securitySchemes:", json.dumps(schema.get("components", {}).get("securitySchemes", {}), indent=2))

    refs = re.findall(r'"#/components/schemas/([^"]+)"', json.dumps(schema))
    defined = set(schema.get("components", {}).get("schemas", {}))
    missing = sorted({r for r in refs if r not in defined})
    print(f"missing schema refs: {missing or 'none'}")

    print("\n=== HTTP endpoints ===")
    client = TestClient(app)
    for path in ("/openapi.json", "/docs", "/redoc"):
        response = client.get(path)
        print(f"{path}: {response.status_code} ({len(response.content)} bytes)")

    print("\n=== Router isolation ===")
    from app.api.v1 import auth, dashboard, projects, users
    from app.api.v1.router_factory import build_crud_router
    from app.crud import contact, customer, milestone, role, stream, task_type, timesheet
    from app.crud.timesheet_entry import timesheet_entry
    from app.schemas.identity import RoleCreate, RoleRead, RoleUpdate
    from app.schemas.organization import (
        ContactCreate,
        ContactRead,
        ContactUpdate,
        CustomerCreate,
        CustomerRead,
        CustomerUpdate,
        StreamCreate,
        StreamRead,
        StreamUpdate,
        TaskTypeCreate,
        TaskTypeRead,
        TaskTypeUpdate,
    )
    from app.schemas.project import MilestoneCreate, MilestoneRead, MilestoneUpdate
    from app.schemas.timesheet import (
        TimesheetCreate,
        TimesheetEntryCreate,
        TimesheetEntryRead,
        TimesheetEntryUpdate,
        TimesheetRead,
        TimesheetUpdate,
    )
    from fastapi import FastAPI

    routers = [
        ("auth", auth.router),
        ("users", users.router),
        ("projects", projects.router),
        ("dashboard", dashboard.router),
    ]
    for name, router in routers:
        probe = FastAPI()
        probe.include_router(router, prefix="/api/v1")
        try:
            probe.openapi()
            print(f"  {name}: OK")
        except Exception as exc:
            print(f"  {name}: FAIL - {exc!r}")


if __name__ == "__main__":
    main()
