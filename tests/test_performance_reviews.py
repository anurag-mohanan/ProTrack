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
    assert len(body["sections"]) >= 1

    team_members = client.get("/api/v1/hr/reviews/team-members", headers=leader_headers)
    assert team_members.status_code == 200, team_members.text
    assert any(row["user_id"] == str(IDS["user_binil"]) for row in team_members.json())

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
