"""One-time migration: set soft-launch password for all active users."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.security import hash_password
from app.crud.auth import reset_login_lock
from app.db.schema_sync import ensure_user_auth_schema
from app.db.session import SessionLocal, engine
from app.models.models import User


def run_migration(*, dry_run: bool = False) -> dict[str, int | list[str]]:
    ensure_user_auth_schema(engine)
    db = SessionLocal()
    updated_emails: list[str] = []
    skipped_deleted = 0
    try:
        users = db.scalars(
            select(User).where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        ).all()
        password_hash = hash_password(SOFT_LAUNCH_PASSWORD)
        for user in users:
            if dry_run:
                updated_emails.append(user.email)
                continue
            user.password_hash = password_hash
            user.must_change_password = True
            reset_login_lock(db, user)
            updated_emails.append(user.email)

        if not dry_run:
            db.commit()

        if dry_run:
            return {
                "updated": len(updated_emails),
                "skipped_deleted": skipped_deleted,
                "emails": updated_emails,
            }

        return {
            "updated": len(updated_emails),
            "skipped_deleted": skipped_deleted,
            "emails": updated_emails,
        }
    finally:
        db.close()


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    result = run_migration(dry_run=dry_run)
    action = "Would update" if dry_run else "Updated"
    print(f"{action} {result['updated']} active user(s) with temporary password.")
    print(f"Password: {SOFT_LAUNCH_PASSWORD}")
    print(
        "Users must change password on first login when INTERNAL_RELEASE=false. "
        "While Internal Release mode is enabled, forced password change is bypassed."
    )
    for email in result["emails"]:
        print(f"  - {email}")


if __name__ == "__main__":
    main()
