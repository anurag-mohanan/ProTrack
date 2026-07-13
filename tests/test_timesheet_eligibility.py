"""Timesheet eligibility — requires_timesheet policy."""

from app.core.permissions import can_write_timesheet_entry, get_role_name
from app.core.timesheet_eligibility import (
    default_requires_timesheet_for_role,
    user_can_enter_own_timesheet,
    user_requires_timesheet,
)
from app.models.models import User
from app.services.timesheet_compliance_service import get_missing_timesheet_rows
from tests.conftest import IDS, login


def test_role_defaults():
    assert default_requires_timesheet_for_role("Designer") is True
    assert default_requires_timesheet_for_role("Design Leader") is True
    assert default_requires_timesheet_for_role("Engineering Manager") is False
    assert default_requires_timesheet_for_role("Admin") is False
    assert default_requires_timesheet_for_role("Planning Board") is False
    assert default_requires_timesheet_for_role("HR") is False
    assert default_requires_timesheet_for_role("Office Administrator") is False
    assert default_requires_timesheet_for_role("Read Only") is False


def test_seeded_users_have_correct_requires_flag(session):
    designer = session.get(User, IDS["user_binil"])
    leader = session.get(User, IDS["user_anurag"])
    admin = session.get(User, IDS["user_admin"])
    em = session.get(User, IDS["user_pm"])
    board = session.get(User, IDS["user_planning_board"])
    assert designer and user_requires_timesheet(designer)
    assert leader and user_requires_timesheet(leader)
    assert admin and not user_requires_timesheet(admin)
    assert em and not user_requires_timesheet(em)
    assert board and not user_requires_timesheet(board)


def test_enter_own_timesheet_policy(session):
    designer = session.get(User, IDS["user_binil"])
    admin = session.get(User, IDS["user_admin"])
    board = session.get(User, IDS["user_planning_board"])
    em = session.get(User, IDS["user_pm"])
    assert designer and user_can_enter_own_timesheet(session, designer)
    assert admin and not user_can_enter_own_timesheet(session, admin)
    assert board and not user_can_enter_own_timesheet(session, board)
    # EM may optionally log
    assert em and user_can_enter_own_timesheet(session, em)
    assert em and can_write_timesheet_entry(session, em)


def test_me_exposes_timesheet_flags(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["requires_timesheet"] is True
    assert body["can_enter_own_timesheet"] is True

    board = login(client, "planning-board@prosohm.com")
    response = client.get("/api/v1/auth/me", headers=board)
    assert response.status_code == 200
    body = response.json()
    assert body["requires_timesheet"] is False
    assert body["can_enter_own_timesheet"] is False


def test_compliance_only_includes_requires_flag(session):
    rows = get_missing_timesheet_rows(session, min_missing_days=1, limit=100)
    ids = {row.user_id for row in rows}
    assert IDS["user_admin"] not in ids
    assert IDS["user_pm"] not in ids
    assert IDS["user_planning_board"] not in ids
    # Delivery users with no recent entries should appear
    assert IDS["user_binil"] in ids or IDS["user_anurag"] in ids


def test_user_override_requires_timesheet(client, session):
    headers = login(client, "admin@prosohm.com")
    # Turn off requirement for a designer
    response = client.patch(
        f"/api/v1/users/{IDS['user_binil']}",
        headers=headers,
        json={"requires_timesheet": False},
    )
    assert response.status_code == 200, response.text
    assert response.json()["requires_timesheet"] is False
    session.expire_all()
    designer = session.get(User, IDS["user_binil"])
    assert designer and not user_requires_timesheet(designer)

    # Restore
    client.patch(
        f"/api/v1/users/{IDS['user_binil']}",
        headers=headers,
        json={"requires_timesheet": True},
    )


def test_planning_board_still_cannot_create_with_module(client, session):
    board = session.get(User, IDS["user_planning_board"])
    assert board
    board.module_access = '["timesheets","planning_board"]'
    board.requires_timesheet = True  # hostile override should not grant write
    session.commit()
    assert not can_write_timesheet_entry(session, board)
    assert not user_can_enter_own_timesheet(session, board)
    assert get_role_name(session, board) == "Planning Board"
