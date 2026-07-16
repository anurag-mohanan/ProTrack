from __future__ import annotations

import uuid

from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember
from tests.conftest import IDS, login


def test_team_leader_can_create_review_and_employee_can_see_it(client, session):
    team = Team(
        id=uuid.uuid4(),
        name="Review Team",
        is_active=True,
        team_lead_id=IDS["user_anurag"],
    )
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=IDS["user_binil"],
            is_primary=True,
            relationship_type=TeamRelationshipType.member,
        )
    )
    session.commit()

    leader_headers = login(client, "anurag@prosohm.com")
    created = client.post(
        "/api/v1/hr/reviews",
        headers=leader_headers,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "FY 2026-27",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["employee_id"] == str(IDS["user_binil"])
    assert body["team_name"] == "Review Team"
    assert len(body["sections"]) == 2
    assert body["sections"][0]["title"] == "Core Competencies"
    assert body["sections"][1]["title"] == "Technical Competencies"
    assert len(body["sections"][0]["items"]) == 9
    assert len(body["sections"][1]["items"]) == 7
    assert body["sections"][0]["items"][0]["guidance"]
    assert "projects" in body
    assert body["review_period_start"] is not None
    assert body["review_period_end"] is not None

    template = client.get("/api/v1/hr/reviews/template", headers=leader_headers)
    assert template.status_code == 200, template.text
    template_body = template.json()
    assert template_body["form_code"] == "PP-HRD-FO-20"
    assert len(template_body["rating_scale"]) == 6
    assert template_body["review_cycle_month"] == 7

    suggestions = client.get(
        f"/api/v1/hr/reviews/suggested-projects?employee_id={IDS['user_binil']}",
        headers=leader_headers,
    )
    assert suggestions.status_code == 200, suggestions.text

    rated = client.patch(
        f"/api/v1/hr/reviews/{body['id']}",
        headers=leader_headers,
        json={
            "sections": [
                {
                    **body["sections"][0],
                    "items": [
                        {**item, "rating": 5 if index == 0 else 4}
                        for index, item in enumerate(body["sections"][0]["items"])
                    ],
                },
                body["sections"][1],
            ]
        },
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["overall_score"] is not None
    assert rated.json()["completion_percent"] > 0

    submitted = client.patch(
        f"/api/v1/hr/reviews/{body['id']}",
        headers=leader_headers,
        json={"status": "submitted"},
    )
    assert submitted.status_code == 200, submitted.text

    employee_headers = login(client, "binil@prosohm.com")
    mine = client.get("/api/v1/hr/reviews/me", headers=employee_headers)
    assert mine.status_code == 200, mine.text
    assert any(row["id"] == body["id"] for row in mine.json())

    ack = client.patch(
        f"/api/v1/hr/reviews/{body['id']}",
        headers=employee_headers,
        json={"acknowledged": True},
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["status"] == "acknowledged"


def test_review_joining_dates_auto_calculate_experience(client, session):
    from datetime import date

    from app.models.models import User

    team = Team(
        id=uuid.uuid4(),
        name="Experience Team",
        is_active=True,
        team_lead_id=IDS["user_anurag"],
    )
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=IDS["user_binil"],
            is_primary=True,
            relationship_type=TeamRelationshipType.member,
        )
    )
    employee = session.get(User, IDS["user_binil"])
    assert employee is not None
    employee.joining_date = date(2024, 1, 15)
    employee.first_job_date = date(2020, 6, 1)
    session.commit()

    leader_headers = login(client, "anurag@prosohm.com")
    created = client.post(
        "/api/v1/hr/reviews",
        headers=leader_headers,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "FY 2025-26",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["employee_joining_date"] == "2024-01-15"
    assert body["employee_first_job_date"] == "2020-06-01"
    assert body["total_experience"]
    assert body["industry_experience"]
    assert body["company_experience"]

    patched = client.patch(
        f"/api/v1/hr/reviews/{body['id']}",
        headers=leader_headers,
        json={
            "employee_joining_date": "2023-07-01",
            "employee_first_job_date": "2018-01-01",
        },
    )
    assert patched.status_code == 200, patched.text
    updated = patched.json()
    assert updated["employee_joining_date"] == "2023-07-01"
    assert updated["employee_first_job_date"] == "2018-01-01"
    assert updated["total_experience"]
    assert updated["industry_experience"]

    session.refresh(employee)
    assert employee.joining_date == date(2023, 7, 1)
    assert employee.first_job_date == date(2018, 1, 1)


def test_non_manager_cannot_delete_review(client, session):
    team = Team(
        id=uuid.uuid4(),
        name="Delete Guard Team",
        is_active=True,
        team_lead_id=IDS["user_anurag"],
    )
    session.add(team)
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=IDS["user_binil"],
            is_primary=True,
            relationship_type=TeamRelationshipType.member,
        )
    )
    session.commit()

    leader_headers = login(client, "anurag@prosohm.com")
    created = client.post(
        "/api/v1/hr/reviews",
        headers=leader_headers,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "Delete test",
        },
    )
    assert created.status_code == 200, created.text
    review_id = created.json()["id"]

    employee_headers = login(client, "binil@prosohm.com")
    denied = client.delete(f"/api/v1/hr/reviews/{review_id}", headers=employee_headers)
    assert denied.status_code == 403

    deleted = client.delete(f"/api/v1/hr/reviews/{review_id}", headers=leader_headers)
    assert deleted.status_code == 204, deleted.text

    missing = client.get(f"/api/v1/hr/reviews/{review_id}", headers=leader_headers)
    assert missing.status_code == 404


def test_non_manager_cannot_create_review_for_other_user(client, session):
    team = Team(id=uuid.uuid4(), name="Protected Review Team", is_active=True)
    session.add(team)
    session.add_all(
        [
            TeamMember(
                team_id=team.id,
                user_id=IDS["user_binil"],
                is_primary=True,
                relationship_type=TeamRelationshipType.member,
            ),
            TeamMember(
                team_id=team.id,
                user_id=IDS["user_junior_designer"],
                is_primary=False,
                relationship_type=TeamRelationshipType.member,
            ),
        ]
    )
    session.commit()

    member_headers = login(client, "binil@prosohm.com")
    denied = client.post(
        "/api/v1/hr/reviews",
        headers=member_headers,
        json={
            "employee_id": str(IDS["user_junior_designer"]),
            "team_id": str(team.id),
            "period_label": "Should fail",
        },
    )
    assert denied.status_code == 403
