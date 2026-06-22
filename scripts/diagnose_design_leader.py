"""Run design_leader lookup diagnostics against the live SQLite DB."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.crud.project import _lookup_user
from app.db.session import SessionLocal
from app.models.models import User

REQUESTED_ID = uuid.UUID("7cf429ba-ca31-4752-9a03-af3ba4700a3a")
STORED_ID = uuid.UUID("7cf429ba-ca31-4752-9a03-afa3ba4700a3")

db = SessionLocal()
try:
    all_users = db.query(User).all()

    print("=== ALL USER IDS ===")
    for u in all_users:
        print(
            "id=", u.id,
            "role_id=", u.role_id,
            "email=", u.email,
            "active=", u.is_active,
        )

    print()
    print("Searching for design leader:", REQUESTED_ID)
    found = _lookup_user(db, REQUESTED_ID)
    print("_lookup_user(requested_id) ->", found)

    print()
    print("Searching for design leader (stored id):", STORED_ID)
    found_stored = _lookup_user(db, STORED_ID)
    print("_lookup_user(stored_id) ->", found_stored)
    if found_stored:
        print("  email=", found_stored.email)

    print()
    print("Exact query: select(User).where(User.id == user_id)")
    stmt = select(User).where(User.id == REQUESTED_ID)
    print("SQL:", stmt)
    print("scalar result:", db.scalar(stmt))
finally:
    db.close()
