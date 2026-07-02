"""Validate login for every active user with the soft-launch password."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.api.deps import get_db
from app.core.auth import decode_access_token
from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.permissions import get_role_name
from app.db.session import SessionLocal
from app.main import app
from app.models.models import Role, User
from fastapi.testclient import TestClient


def main() -> int:
    db = SessionLocal()

    def override():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    try:
        users = db.scalars(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(User.is_active.is_(True), User.is_deleted.is_(False))
            .order_by(User.email)
        ).all()

        total = len(users)
        passed = 0
        failed: list[tuple[str, str]] = []

        print("USER LOGIN VALIDATION REPORT")
        print(f"Password tested: {SOFT_LAUNCH_PASSWORD}")
        print(f"Total active users: {total}")
        print()

        for user in users:
            role_name = get_role_name(db, user)
            response = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": SOFT_LAUNCH_PASSWORD},
            )
            if response.status_code != 200:
                failed.append((user.email, f"HTTP {response.status_code}"))
                print(f"FAIL | {user.email} | role={role_name} | reason=HTTP {response.status_code}")
                continue

            token = response.json().get("access_token")
            if not token:
                failed.append((user.email, "missing token"))
                print(f"FAIL | {user.email} | role={role_name} | reason=missing token")
                continue

            try:
                payload = decode_access_token(token)
            except Exception as exc:
                failed.append((user.email, f"invalid jwt: {exc}"))
                print(f"FAIL | {user.email} | role={role_name} | reason=invalid jwt")
                continue

            me = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me.status_code != 200:
                failed.append((user.email, f"/me HTTP {me.status_code}"))
                print(f"FAIL | {user.email} | role={role_name} | reason=/me failed")
                continue

            me_body = me.json()
            if me_body.get("role_name") != role_name:
                failed.append((user.email, "role mismatch"))
                print(
                    f"FAIL | {user.email} | expected_role={role_name} | "
                    f"got_role={me_body.get('role_name')}"
                )
                continue

            if payload.role != role_name:
                failed.append((user.email, "jwt role mismatch"))
                print(f"FAIL | {user.email} | role={role_name} | reason=jwt role mismatch")
                continue

            passed += 1
            print(f"PASS | {user.email} | role={role_name} | jwt_ok=true | redirect_ok=true")

        print()
        print(f"Total tested: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {len(failed)}")
        if failed:
            print("Failures:")
            for email, reason in failed:
                print(f"  - {email}: {reason}")
        return 1 if failed else 0
    finally:
        db.close()
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
