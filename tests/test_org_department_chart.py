"""Organization department hierarchy for the org chart."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.models import OrgDepartment, Team, TeamMember, User
from tests.conftest import IDS


def test_organization_chart_returns_departments(client, session):
    eng = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "engineering"))
    hr = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "hr_admin"))
    assert eng is not None
    assert hr is not None

    team = Team(
        id=uuid.uuid4(),
        name="Dept Chart Delivery",
        colour="#004d40",
        is_active=True,
        org_department_id=eng.id,
    )
    session.add(team)
    user = session.get(User, IDS["user_binil"])
    assert user is not None
    user.org_department_id = eng.id
    user.team_id = team.id
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=user.id,
            role_within_team="Designer",
            is_primary=True,
            is_billable_headcount=True,
        )
    )
    session.commit()

    response = client.get(
        "/api/v1/teams/organization-chart",
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "departments" in payload
    codes = {row["code"] for row in payload["departments"]}
    assert {"engineering", "hr_admin", "management", "sales", "it"} <= codes

    engineering = next(row for row in payload["departments"] if row["code"] == "engineering")
    team_names = {row["team_name"] for row in engineering["teams"]}
    assert "Dept Chart Delivery" in team_names
    assert any(
        person["user_id"] == str(user.id)
        for team_row in engineering["teams"]
        for person in team_row["people"]
    )


def test_office_administrator_lands_in_hr_department(client, session):
    from app.models.models import Role

    hr = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "hr_admin"))
    assert hr is not None
    oa_role = session.scalar(select(Role).where(Role.name == "Office Administrator"))
    if oa_role is None:
        oa_role = Role(id=uuid.uuid4(), name="Office Administrator", description="Office admin")
        session.add(oa_role)
        session.flush()

    person = User(
        id=uuid.uuid4(),
        role_id=oa_role.id,
        email="chandrashekhar.orgchart@prosohm.com",
        password_hash="x",
        first_name="Chandrashekhar",
        last_name="J",
        designation="Office Administrator",
        is_active=True,
        org_department_id=hr.id,
    )
    corporate = session.scalar(select(Team).where(Team.name == "Corporate / Management"))
    if corporate is None:
        corporate = Team(
            id=uuid.uuid4(),
            name="Corporate / Management",
            colour="#607d8b",
            is_active=True,
        )
        session.add(corporate)
        session.flush()
    session.add(person)
    session.add(
        TeamMember(
            team_id=corporate.id,
            user_id=person.id,
            role_within_team="Office Administrator",
            is_primary=True,
            is_billable_headcount=False,
        )
    )
    session.commit()

    response = client.get(
        "/api/v1/teams/organization-chart",
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    hr_dept = next(row for row in payload["departments"] if row["code"] == "hr_admin")
    names = {row["name"] for row in [*hr_dept["leaders"], *hr_dept["staff"]]}
    assert "Chandrashekhar J" in names
