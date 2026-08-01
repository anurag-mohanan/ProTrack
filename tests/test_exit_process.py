"""Exit process — generic employee exit interview (PP-HRD-FO-30)."""

from datetime import date, timedelta

from sqlalchemy import select

from app.models.models import TeamMember, User
from tests.conftest import IDS, login


def test_exit_interview_form_and_crud(client, session):
    headers = login(client, "admin@prosohm.com")

    form = client.get("/api/v1/hr/exit-process/form", headers=headers)
    assert form.status_code == 200, form.text
    questions = form.json()
    assert len(questions) >= 8
    assert any(q["id"] == "reason_for_leaving" for q in questions)

    create = client.post(
        "/api/v1/hr/exit-process",
        headers=headers,
        json={
            "employee_name": "Exit Test Person",
            "employee_user_id": str(IDS["user_binil"]),
            "designation": "Designer",
            "last_working_date": "2026-08-15",
            "interview_date": "2026-08-10",
            "answers": {
                "reason_for_leaving": "Career growth / new opportunity",
                "overall_experience": 4,
            },
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["form_code"] == "PP-HRD-FO-30"
    assert body["status"] == "draft"
    assert body["answers"]["reason_for_leaving"] == "Career growth / new opportunity"
    assert len(body["questions"]) >= 8
    interview_id = body["id"]

    listed = client.get("/api/v1/hr/exit-process?status=draft", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == interview_id for row in listed.json())

    # Complete without confirm → 422
    denied = client.patch(
        f"/api/v1/hr/exit-process/{interview_id}",
        headers=headers,
        json={
            "status": "completed",
            "attitude_was_good": True,
            "skillset_rating": 4,
            "eligible_for_rehire": "yes",
        },
    )
    assert denied.status_code == 422

    patched = client.patch(
        f"/api/v1/hr/exit-process/{interview_id}",
        headers=headers,
        json={
            "status": "completed",
            "confirm_left_organisation": True,
            "attitude_was_good": True,
            "skillset_rating": 4,
            "eligible_for_rehire": "yes",
            "answers": {"additional_comments": "All the best."},
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"
    assert patched.json()["answers"]["additional_comments"] == "All the best."
    assert patched.json()["answers"]["reason_for_leaving"] == "Career growth / new opportunity"
    assert patched.json()["completed_at"] is not None
    # Interview date becomes last working day
    assert patched.json()["last_working_date"] == "2026-08-10"
    assert patched.json()["attitude_was_good"] is True
    assert patched.json()["skillset_rating"] == 4
    assert patched.json()["eligible_for_rehire"] == "yes"

    # Already completed — cannot delete after we publish in other test; here still draft publish path
    # Soft-deleted only if not published
    deleted = client.delete(f"/api/v1/hr/exit-process/{interview_id}", headers=headers)
    assert deleted.status_code == 204


def test_exit_complete_requires_assessment_fields(client):
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/exit-process",
        headers=headers,
        json={
            "employee_name": "No Assessment",
            "interview_date": date.today().isoformat(),
        },
    )
    assert created.status_code == 201
    interview_id = created.json()["id"]

    missing = client.patch(
        f"/api/v1/hr/exit-process/{interview_id}",
        headers=headers,
        json={"status": "completed", "confirm_left_organisation": True},
    )
    assert missing.status_code == 422
    assert "attitude" in str(missing.json()["detail"]).lower()


def test_exit_complete_offboards_linked_employee(client, session):
    headers = login(client, "admin@prosohm.com")
    # Fresh user with team so offboard is observable
    team = client.post(
        "/api/v1/teams",
        json={"name": "Exit Offboard Team", "colour": "#112233", "is_active": True},
        headers=headers,
    ).json()
    roles = client.get("/api/v1/roles", headers=headers).json()
    role_items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    designer = next(r for r in role_items if r["name"] == "Designer")
    create_user = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer["id"],
            "email": f"exit.offboard.{date.today().toordinal()}@prosohm.com",
            "password": "TempPass@123",
            "first_name": "Exit",
            "last_name": "Offboard",
            "is_active": True,
            "employment_type": "full_time",
            "team_id": team["id"],
        },
    )
    assert create_user.status_code == 201, create_user.text
    user_id = create_user.json()["id"]

    interview_day = date.today() - timedelta(days=1)
    created = client.post(
        "/api/v1/hr/exit-process",
        headers=headers,
        json={
            "employee_name": "Exit Offboard",
            "employee_user_id": user_id,
            "interview_date": interview_day.isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    interview_id = created.json()["id"]

    completed = client.patch(
        f"/api/v1/hr/exit-process/{interview_id}",
        headers=headers,
        json={
            "status": "completed",
            "confirm_left_organisation": True,
            "attitude_was_good": False,
            "skillset_rating": 3,
            "eligible_for_rehire": "conditional",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["last_working_date"] == interview_day.isoformat()
    assert completed.json()["eligible_for_rehire"] == "conditional"

    session.expire_all()
    from uuid import UUID

    user = session.get(User, UUID(user_id))
    assert user is not None
    assert user.leaving_date == interview_day
    assert user.is_archived is True
    assert user.offboard_applied_at is not None
    assert (
        list(session.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all())
        == []
    )


def test_exit_process_forbidden_for_designer(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/hr/exit-process", headers=headers)
    assert response.status_code == 403


def test_published_exit_interview_cannot_be_deleted(client, session):
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/exit-process",
        headers=headers,
        json={
            "employee_name": "Published Exit",
            "employee_user_id": str(IDS["user_binil"]),
            "answers": {"reason_for_leaving": "Career growth / new opportunity"},
        },
    )
    assert created.status_code == 201, created.text
    interview_id = created.json()["id"]
    assert created.json()["is_published"] is False

    published = client.post(f"/api/v1/hr/exit-process/{interview_id}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()["is_published"] is True

    deleted = client.delete(f"/api/v1/hr/exit-process/{interview_id}", headers=headers)
    assert deleted.status_code == 400
