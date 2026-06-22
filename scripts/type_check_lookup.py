"""Exercise _lookup_user with ProjectCreate parsing (same types as POST /projects)."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crud.project import _lookup_user
from app.db.session import SessionLocal
from app.models.models import User
from app.schemas.project import ProjectCreate

WRONG_ID = "7cf429ba-ca31-4752-9a03-af3ba4700a3a"
CORRECT_ID = "7cf429ba-ca31-4752-9a03-afa3ba4700a3"

payload = {
    "tool_number": "T-1",
    "part_description": "Part",
    "customer_id": "3946c135-d515-4bbd-affb-00b5c1893832",
    "customer_contact_id": "b5301223-164f-4035-8017-252ff0452fa6",
    "design_leader_id": WRONG_ID,
    "stream_id": "a4b9ba7c-4ff4-4a2c-8dc7-823a7cfacb55",
    "code": "TYPE-CHECK",
    "quoted_hours": 1,
    "due_date": "2026-07-01",
}

obj_in = ProjectCreate(**payload)
print("ProjectCreate.design_leader_id =", obj_in.design_leader_id)
print("type(ProjectCreate.design_leader_id) =", type(obj_in.design_leader_id))
print()

db = SessionLocal()
try:
    u = db.query(User).filter(User.email == "anurag@prosohm.com").one()
    print("DB User.id =", u.id)
    print("type(DB User.id) =", type(u.id))
    print("User.id field column type:", User.__table__.c.id.type)
    print()

    print("--- lookup with ProjectCreate UUID (wrong id from request) ---")
    _lookup_user(db, obj_in.design_leader_id)

    print()
    print("--- lookup with actual DB UUID ---")
    _lookup_user(db, u.id)

    print()
    print("IDs equal?", obj_in.design_leader_id == u.id)
    print("Wrong == correct string?", WRONG_ID == CORRECT_ID)
finally:
    db.close()
