"""Assign the soft-launch temporary password to all active imported users."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.models import User

SOFT_LAUNCH_PASSWORD = "Prosohm@2026"


def main() -> None:
    db = SessionLocal()
    try:
        users = db.scalars(
            select(User).where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        ).all()
        if not users:
            print("No active users found.")
            return

        password_hash = hash_password(SOFT_LAUNCH_PASSWORD)
        for user in users:
            user.password_hash = password_hash
            user.must_change_password = True
            db.add(user)

        db.commit()
        print(f"Updated {len(users)} active user(s) with soft-launch temporary password.")
        print("Users must change password on first login.")
        for user in users:
            print(f"  - {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
