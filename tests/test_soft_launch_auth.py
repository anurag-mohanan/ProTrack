from sqlalchemy import select

from app.core.auth import decode_access_token
from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.permissions import get_role_name
from app.core.security import hash_password
from app.crud.auth import reset_login_lock
from app.models.enums import ActivityAction
from app.models.models import Activity, Role, User
from tests.conftest import DEFAULT_PASSWORD, IDS, login

SOFT_LAUNCH_PASSWORD_TEST = SOFT_LAUNCH_PASSWORD


def test_login_sets_last_login(client):
    headers = login(client, "admin@prosohm.com")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["last_login"] is not None


def test_failed_login_is_audited(client, session):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@prosohm.com", "password": "WrongPass@123"},
    )
    assert response.status_code == 401
    activity = session.scalar(
        select(Activity)
        .where(Activity.action == ActivityAction.login_failed)
        .order_by(Activity.created_at.desc())
    )
    assert activity is not None
    assert activity.new_value == "admin@prosohm.com:wrong_password"


def test_change_password_requires_confirmation(client):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "NewPass@1234",
            "confirm_password": "Mismatch@1234",
        },
    )
    assert response.status_code == 422


def test_change_password_enforces_policy(client):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "weakpass",
            "confirm_password": "weakpass",
        },
    )
    assert response.status_code == 422


def test_force_password_change(client):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        f"/api/v1/users/{IDS['user_binil']}/force-password-change",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


def test_admin_impersonation_flow(client):
    admin_headers = login(client, "admin@prosohm.com")
    start = client.post(
        f"/api/v1/auth/impersonate/{IDS['user_binil']}",
        headers=admin_headers,
    )
    assert start.status_code == 200
    impersonation_headers = {"Authorization": f"Bearer {start.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=impersonation_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "binil@prosohm.com"
    assert me.json()["impersonator_id"] == str(IDS["user_admin"])

    stop = client.post("/api/v1/auth/stop-impersonation", headers=impersonation_headers)
    assert stop.status_code == 200
    admin_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {stop.json()['access_token']}"},
    )
    assert admin_me.json()["email"] == "admin@prosohm.com"


def test_soft_launch_password_login(client):
    admin_headers = login(client, "admin@prosohm.com")
    client.post(
        f"/api/v1/users/{IDS['user_binil']}/reset-password",
        headers=admin_headers,
        json={"password": SOFT_LAUNCH_PASSWORD_TEST},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "binil@prosohm.com", "password": SOFT_LAUNCH_PASSWORD_TEST},
    )
    assert response.status_code == 200
    user_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.json()["must_change_password"] is True

    change = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={
            "current_password": SOFT_LAUNCH_PASSWORD_TEST,
            "new_password": "Designer@2026",
            "confirm_password": "Designer@2026",
        },
    )
    assert change.status_code == 200
    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.json()["must_change_password"] is False


def test_role_logins(client):
    role_users = [
        ("admin@prosohm.com", "Admin"),
        ("pm@prosohm.com", "Engineering Manager"),
        ("anurag@prosohm.com", "Design Leader"),
        ("binil@prosohm.com", "Designer"),
        ("ranjith@prosohm.com", "Surfacer"),
        ("readonly@prosohm.com", "Read Only"),
    ]
    for email, expected_role in role_users:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 200, email
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert me.json()["role_name"] == expected_role, email


def test_all_active_users_can_login_with_temp_password(client, session):
    password_hash = hash_password(SOFT_LAUNCH_PASSWORD_TEST)
    active_users = session.scalars(
        select(User).where(User.is_active.is_(True), User.is_deleted.is_(False))
    ).all()
    for user in active_users:
        user.password_hash = password_hash
        user.must_change_password = True
        reset_login_lock(session, user)

    failures: list[str] = []
    for user in active_users:
        expected_role = get_role_name(session, user)
        response = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": SOFT_LAUNCH_PASSWORD_TEST},
        )
        if response.status_code != 200:
            failures.append(f"{user.email}: HTTP {response.status_code}")
            continue

        token = response.json()["access_token"]
        payload = decode_access_token(token)
        assert payload.sub == user.id
        assert payload.role == expected_role
        assert payload.email == user.email

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if me.status_code != 200:
            failures.append(f"{user.email}: /me HTTP {me.status_code}")
            continue
        if me.json()["role_name"] != expected_role:
            failures.append(
                f"{user.email}: expected role {expected_role}, got {me.json()['role_name']}"
            )

    assert not failures, "\n".join(failures)


def test_locked_user_cannot_login(client, session):
    user = session.get(User, IDS["user_binil"])
    user.is_locked = True
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "binil@prosohm.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 401


def test_unlock_user_restores_login(client, session):
    user = session.get(User, IDS["user_binil"])
    user.is_locked = True
    user.failed_login_count = 3
    session.add(user)
    session.commit()

    admin_headers = login(client, "admin@prosohm.com")
    unlock = client.post(
        f"/api/v1/users/{IDS['user_binil']}/unlock",
        headers=admin_headers,
    )
    assert unlock.status_code == 200
    assert unlock.json()["is_locked"] is False
    assert unlock.json()["failed_login_count"] == 0

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "binil@prosohm.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
