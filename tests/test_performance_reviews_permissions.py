from __future__ import annotations

import uuid

from app.models.enums import TeamRelationshipType
from app.models.models import Team, TeamMember
from tests.conftest import IDS, login


def test_admin_can_create_and_edit_review(client, session):
    team = Team(
        id=uuid.uuid4(),
        name="Admin Review Team",
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

    admin_headers = login(client, "admin@prosohm.com")
    members = client.get("/api/v1/hr/reviews/team-members", headers=admin_headers)
    assert members.status_code == 200, members.text
    assert len(members.json()) > 0

    created = client.post(
        "/api/v1/hr/reviews",
        headers=admin_headers,
        json={
            "employee_id": str(IDS["user_binil"]),
            "team_id": str(team.id),
            "period_label": "FY 2026-27",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["can_edit_manager_section"] is True
    assert body["is_editable"] is True

    patched = client.patch(
        f"/api/v1/hr/reviews/{body['id']}",
        headers=admin_headers,
        json={
            "sections": [
                {
                    **body["sections"][0],
                    "items": [
                        {**item, "rating": 4}
                        for item in body["sections"][0]["items"]
                    ],
                },
                body["sections"][1],
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["completion_percent"] > 0


def test_employee_can_save_self_ratings_during_self_stage(client, session):
    team = Team(
        id=uuid.uuid4(),
        name="Self Rating Team",
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
    review_id = created.json()["id"]

    employee_headers = login(client, "binil@prosohm.com")
    mine = client.get(f"/api/v1/hr/reviews/{review_id}", headers=employee_headers)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["can_edit_employee_section"] is True
    assert body["is_editable"] is True

    rated = client.patch(
        f"/api/v1/hr/reviews/{review_id}",
        headers=employee_headers,
        json={
            "sections": [
                {
                    **body["sections"][0],
                    "items": [
                        {**item, "rating": 5 if index == 0 else 3}
                        for index, item in enumerate(body["sections"][0]["items"])
                    ],
                },
                body["sections"][1],
            ],
            "employee_summary": "Self review notes",
        },
    )
    assert rated.status_code == 200, rated.text
    saved = rated.json()
    assert saved["employee_summary"] == "Self review notes"
    assert float(saved["sections"][0]["items"][0]["rating"]) == 5.0
    assert saved["completion_percent"] > 0
