"""Simulate POST /projects through CRUDProject.create() and print diagnostics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crud.project import project
from app.db.session import SessionLocal
from app.schemas.project import ProjectCreate

# Wrong ID seen in 422 errors (typo)
WRONG_DESIGN_LEADER = "7cf429ba-ca31-4752-9a03-af3ba4700a3a"
# Correct ID from GET /users / DB
CORRECT_DESIGN_LEADER = "7cf429ba-ca31-4752-9a03-afa3ba4700a3"

for label, leader_id in [
    ("WRONG_ID (from failing requests)", WRONG_DESIGN_LEADER),
    ("CORRECT_ID (from GET /users)", CORRECT_DESIGN_LEADER),
]:
    print("\n" + "=" * 60)
    print(f"TEST: {label}")
    print("=" * 60)

    payload = {
        "tool_number": "T-DBG",
        "part_description": "Debug part",
        "customer_id": "3946c135-d515-4bbd-affb-00b5c1893832",
        "customer_contact_id": "b5301223-164f-4035-8017-252ff0452fa6",
        "design_leader_id": leader_id,
        "stream_id": "a4b9ba7c-4ff4-4a2c-8dc7-823a7cfacb55",
        "code": f"DBG-{leader_id[:8]}",
        "quoted_hours": 1,
        "due_date": "2026-07-01",
    }

    obj_in = ProjectCreate(**payload)
    db = SessionLocal()
    try:
        project.create(db, obj_in=obj_in)
        print(f"RESULT: SUCCESS for {label}")
    except Exception as exc:
        print(f"RESULT: FAILED for {label}")
        print(f"  exception={exc}")
    finally:
        db.close()
