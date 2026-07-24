"""Employee training — onboarding gate, assignments, process audit."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from app.db.phase62_employee_training_schema_sync import seed_common_training_courses
from app.models.training import TrainingCourse
from app.services.hr_process_audit_service import build_process_audit
from app.services.training_service import incomplete_required_for_user


def test_common_courses_seeded(session):
    created = seed_common_training_courses(session)
    assert created >= 1 or session.scalar(select(TrainingCourse).limit(1)) is not None
    required = session.scalars(
        select(TrainingCourse).where(TrainingCourse.is_required_for_onboarding.is_(True))
    ).all()
    assert len(required) >= 5


def test_onboarding_assigns_required_trainings_and_blocks_complete(
    client, session, auth_headers
):
    seed_common_training_courses(session)

    created = client.post(
        "/api/v1/hr/onboarding",
        headers=auth_headers,
        json={
            "employee_name": "Trainee One",
            "employee_email": "trainee.one@prosohm.com",
            "joining_date": date.today().isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    user_id = body["employee_user_id"]
    assert user_id

    open_rows = incomplete_required_for_user(session, UUID(user_id))
    assert len(open_rows) >= 5

    saw_training_block = False
    for item in body["items"]:
        if item["status"] == "not_applicable":
            continue
        resp = client.post(
            f"/api/v1/hr/onboarding/{body['id']}/items/{item['id']}/status",
            headers=auth_headers,
            json={"status": "completed"},
        )
        if resp.status_code == 422:
            saw_training_block = True
            assert "training" in resp.json()["detail"].lower()
            break
        assert resp.status_code == 200, resp.text

    final = client.get(f"/api/v1/hr/onboarding/{body['id']}", headers=auth_headers)
    assert final.status_code == 200
    assert final.json()["status"] == "in_progress"
    assert saw_training_block or incomplete_required_for_user(session, UUID(user_id))

    assignments = client.get(
        f"/api/v1/hr/training/assignments?user_id={user_id}",
        headers=auth_headers,
    )
    assert assignments.status_code == 200
    for row in assignments.json():
        if row["status"] == "completed":
            continue
        done = client.post(
            f"/api/v1/hr/training/assignments/{row['id']}/complete",
            headers=auth_headers,
        )
        assert done.status_code == 200, done.text

    checklist = client.get(
        f"/api/v1/hr/onboarding/{body['id']}", headers=auth_headers
    ).json()
    for item in checklist["items"]:
        if item["status"] == "pending":
            resp = client.post(
                f"/api/v1/hr/onboarding/{body['id']}/items/{item['id']}/status",
                headers=auth_headers,
                json={"status": "completed"},
            )
            assert resp.status_code == 200, resp.text

    finished = client.get(f"/api/v1/hr/onboarding/{body['id']}", headers=auth_headers)
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"


def test_adhoc_assign_and_audit_overdue(client, session, auth_headers):
    seed_common_training_courses(session)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()

    course = client.post(
        "/api/v1/hr/training/courses",
        headers=auth_headers,
        json={
            "code": "ADHOC_SAFE",
            "title": "Ad-hoc safety refresh",
            "estimated_minutes": 15,
            "is_required_for_onboarding": False,
        },
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    due = (date.today() - timedelta(days=1)).isoformat()
    assigned = client.post(
        "/api/v1/hr/training/assign",
        headers=auth_headers,
        json={"course_id": course_id, "user_ids": [me["id"]], "due_date": due},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()

    audit = build_process_audit(session, as_of=date.today())
    flags = {item["flag"] for item in audit["items"]}
    assert "incomplete_training" in flags

    assignment_id = assigned.json()[0]["id"]
    client.post(
        f"/api/v1/hr/training/assignments/{assignment_id}/complete",
        headers=auth_headers,
    )
    # Expire so audit sees committed completion from API session
    session.expire_all()
    audit2 = build_process_audit(session, as_of=date.today())
    overdue_for_me = [
        item
        for item in audit2["items"]
        if item["flag"] == "incomplete_training"
        and item.get("subject_user_id") == me["id"]
        and "Ad-hoc safety" in (item.get("detail") or "")
    ]
    assert overdue_for_me == []
