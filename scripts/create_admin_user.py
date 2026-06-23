"""Create or reset the ProTrack admin user in the existing database."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 — register models
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.models import Role, User

ADMIN_EMAIL = "admin@prosohm.com"
ADMIN_PASSWORD = "Password@123"
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "User"
ADMIN_ROLE_NAME = "Admin"


def get_or_create_admin_role(db) -> Role:
    role = db.query(Role).filter(Role.name == ADMIN_ROLE_NAME).one_or_none()
    if role is not None:
        return role

    role = Role(
        name=ADMIN_ROLE_NAME,
        description="Full system administration",
    )
    db.add(role)
    db.flush()
    return role


def create_or_update_admin_user() -> None:
    db = SessionLocal()
    try:
        admin_role = get_or_create_admin_role(db)
        password_hash = hash_password(ADMIN_PASSWORD)

        existing_user = (
            db.query(User).filter(User.email == ADMIN_EMAIL).one_or_none()
        )

        if existing_user is not None:
            existing_user.role_id = admin_role.id
            existing_user.password_hash = password_hash
            existing_user.first_name = ADMIN_FIRST_NAME
            existing_user.last_name = ADMIN_LAST_NAME
            existing_user.is_active = True
            admin_user = existing_user
            action = "updated"
        else:
            admin_user = User(
                role_id=admin_role.id,
                email=ADMIN_EMAIL,
                password_hash=password_hash,
                first_name=ADMIN_FIRST_NAME,
                last_name=ADMIN_LAST_NAME,
                is_active=True,
            )
            db.add(admin_user)
            action = "created"

        db.commit()
        db.refresh(admin_user)

        print("Admin user ready.")
        print(f"  Action: {action}")
        print(f"  User ID: {admin_user.id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Role: {admin_role.name}")
        print()
        print("Login test summary:")
        print(f"  Email: {ADMIN_EMAIL}")
        print(f"  Password: {ADMIN_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_or_update_admin_user()
