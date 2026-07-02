"""Audit user authentication readiness without exposing password hashes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.models import Role, User

SOFT_LAUNCH_PASSWORD = "Prosohm@2026"
LEGACY_PASSWORD = "Password@123"


def main() -> int:
    db = SessionLocal()
    try:
        users = db.scalars(
            select(User).join(Role, User.role_id == Role.id).order_by(User.email)
        ).all()
        print(f"Total users: {len(users)}")
        print()
        passed = failed = skipped = 0
        for user in users:
            role = db.get(Role, user.role_id)
            role_name = role.name if role else "Unknown"
            password_hash = user.password_hash or ""
            is_bcrypt = password_hash.startswith("$2")
            matches_soft_launch = (
                verify_password(SOFT_LAUNCH_PASSWORD, password_hash)
                if password_hash
                else False
            )
            matches_legacy = (
                verify_password(LEGACY_PASSWORD, password_hash) if password_hash else False
            )
            issues: list[str] = []
            if user.is_deleted:
                issues.append("deleted")
            if not user.is_active:
                issues.append("inactive")
            if user.is_archived:
                issues.append("archived")
            if not password_hash:
                issues.append("missing_hash")
            elif not is_bcrypt:
                issues.append("invalid_hash_format")
            elif not matches_soft_launch and not matches_legacy:
                issues.append("password_mismatch")

            if user.is_deleted:
                status = "SKIP"
                skipped += 1
            elif not user.is_active or user.is_archived:
                status = "SKIP"
                skipped += 1
            elif matches_soft_launch and is_bcrypt:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(
                f"{status} | {user.email} | role={role_name} | "
                f"active={user.is_active} | archived={user.is_archived} | "
                f"deleted={user.is_deleted} | must_change={user.must_change_password} | "
                f"soft_launch_pwd={matches_soft_launch} | legacy_pwd={matches_legacy} | "
                f"issues={','.join(issues) or 'none'}"
            )

        print()
        print(f"Summary: passed={passed}, failed={failed}, skipped={skipped}")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
