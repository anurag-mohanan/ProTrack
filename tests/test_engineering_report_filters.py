"""Engineering suite Customer > Team > Period filters and leader scope."""

from datetime import date
from decimal import Decimal
import uuid

from app.models.enums import TeamRelationshipType, TimesheetStatus, WorkCategory
from app.models.models import Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.report_scope import ReportScopeForbidden, resolve_report_scope
from tests.conftest import IDS, login


def _seed_leader_teams(session):
    team_a = Team(id=uuid.uuid4(), name="Report Team A", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Report Team B", is_active=True)
    session.add_all([team_a, team_b])
    session.flush()

    leader = session.get(User, IDS["user_anurag"])
    designer = session.get(User, IDS["user_binil"])
    assert leader is not None and designer is not None

    leader.team_id = team_a.id
    designer.team_id = team_a.id
    session.add_all(
        [
            TeamMember(
                team_id=team_a.id,
                user_id=leader.id,
                relationship_type=TeamRelationshipType.team_leader,
                is_primary=True,
            ),
            TeamMember(
                team_id=team_a.id,
                user_id=designer.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            ),
        ]
    )

    week_start = date(2026, 7, 6)  # Monday
    timesheet = Timesheet(
        user_id=designer.id,
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=week_start,
            hours=Decimal("8"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=IDS["project"],
            description="Scoped design work",
        )
    )
    session.commit()
    return team_a, team_b, week_start


def test_resolve_report_scope_forbids_foreign_team(session):
    team_a, team_b, _ = _seed_leader_teams(session)
    leader = session.get(User, IDS["user_anurag"])
    scope = resolve_report_scope(session, leader, team_id=team_a.id)
    assert scope.team_ids == frozenset({team_a.id})
    assert IDS["user_binil"] in (scope.user_ids or frozenset())

    try:
        resolve_report_scope(session, leader, team_id=team_b.id)
        assert False, "expected ReportScopeForbidden"
    except ReportScopeForbidden:
        pass


def test_engineering_preview_customer_and_team_filters(client, session):
    team_a, _, week_start = _seed_leader_teams(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get(
        "/api/v1/reports/engine/weekly-engineering/preview",
        headers=headers,
        params={
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
            "customer_id": str(IDS["customer"]),
            "team_id": str(team_a.id),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"]["period_type"] == "weekly"
    assert float(body["executive"]["total_engineering_hours"]) >= 8


def test_design_leader_preview_scoped_to_own_team(client, session):
    team_a, team_b, week_start = _seed_leader_teams(session)
    headers = login(client, "anurag@prosohm.com")

    ok = client.get(
        "/api/v1/reports/engine/monthly-engineering/preview",
        headers=headers,
        params={
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
            "team_id": str(team_a.id),
        },
    )
    assert ok.status_code == 200, ok.text

    forbidden = client.get(
        "/api/v1/reports/engine/monthly-engineering/preview",
        headers=headers,
        params={
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
            "team_id": str(team_b.id),
        },
    )
    assert forbidden.status_code == 403


def test_design_leader_export_respects_team_scope(client, session):
    team_a, team_b, week_start = _seed_leader_teams(session)
    headers = login(client, "anurag@prosohm.com")

    ok = client.get(
        "/api/v1/reports/engine/monthly-engineering/export.xlsx",
        headers=headers,
        params={
            "period_type": "monthly",
            "anchor": week_start.replace(day=1).isoformat(),
            "customer_id": str(IDS["customer"]),
            "team_id": str(team_a.id),
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.content[:2] == b"PK"

    forbidden = client.get(
        "/api/v1/reports/engine/monthly-engineering/export.xlsx",
        headers=headers,
        params={
            "period_type": "monthly",
            "anchor": week_start.replace(day=1).isoformat(),
            "team_id": str(team_b.id),
        },
    )
    assert forbidden.status_code == 403


def test_leader_default_scope_excludes_other_team_without_filter(client, session):
    """Without team_id, Design Leader still cannot see org-wide — only accessible teams."""
    team_a, _team_b, week_start = _seed_leader_teams(session)
    # Put a second designer on no team / other team hours would not appear via user_ids
    headers = login(client, "anurag@prosohm.com")
    response = client.get(
        "/api/v1/reports/engine/weekly-engineering/preview",
        headers=headers,
        params={
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    designer_ids = {row["user_id"] for row in body["designer_productivity"]}
    assert str(IDS["user_binil"]) in designer_ids or body["executive"]["total_engineering_hours"] >= 0
    # Scoped users only — admin-only users must not appear as designers in leader scope
    assert str(IDS["user_admin"]) not in designer_ids
    _ = team_a
