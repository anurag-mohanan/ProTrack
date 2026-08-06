"""Team-based timesheet report subject authorization."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import TeamRelationshipType, TimesheetStatus, WorkCategory
from app.models.models import Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.report_authorization import (
    ReportSubjectMode,
    resolve_report_authority,
    resolve_report_subject_user_ids,
    resolve_report_team_ids,
)
from app.services.reporting.report_scope import (
    ReportScopeForbidden,
    refine_scope_for_period,
    resolve_report_scope,
)
from tests.conftest import IDS, login


def _seed_member_and_leader(session):
    team_a = Team(id=uuid.uuid4(), name="Auth Team A", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Auth Team B", is_active=True)
    session.add_all([team_a, team_b])
    session.flush()

    leader = session.get(User, IDS["user_anurag"])
    member = session.get(User, IDS["user_binil"])
    assert leader is not None and member is not None

    leader.team_id = team_a.id
    member.team_id = team_a.id
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
                user_id=member.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            ),
            TeamMember(
                team_id=team_b.id,
                user_id=member.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=False,
            ),
        ]
    )
    session.commit()
    return team_a, team_b, leader, member


def test_team_member_report_authority_is_own_only(session):
    _, _, _, member = _seed_member_and_leader(session)
    auth = resolve_report_authority(session, member)
    assert auth.mode == ReportSubjectMode.own
    assert auth.own_only is True
    assert resolve_report_team_ids(session, member) == frozenset()
    assert resolve_report_subject_user_ids(session, member) == {member.id}

    scope = resolve_report_scope(session, member)
    assert scope.subject_mode == ReportSubjectMode.own
    assert scope.user_ids == frozenset({member.id})

    refined = refine_scope_for_period(
        session,
        scope,
        range_start=date(2026, 7, 1),
        range_end=date(2026, 7, 31),
    )
    assert refined.user_ids == frozenset({member.id})


def test_team_leader_report_authority_led_teams_only(session):
    team_a, team_b, leader, member = _seed_member_and_leader(session)
    auth = resolve_report_authority(session, leader)
    assert auth.mode == ReportSubjectMode.teams
    assert auth.team_ids == frozenset({team_a.id})
    assert team_b.id not in (auth.team_ids or frozenset())

    scope = resolve_report_scope(session, leader, team_id=team_a.id)
    assert member.id in (scope.user_ids or frozenset())

    try:
        resolve_report_scope(session, leader, team_id=team_b.id)
        assert False, "expected ReportScopeForbidden"
    except ReportScopeForbidden:
        pass


def test_admin_report_authority_unrestricted(session):
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    auth = resolve_report_authority(session, admin)
    assert auth.unrestricted is True
    assert resolve_report_team_ids(session, admin) is None
    assert resolve_report_subject_user_ids(session, admin) is None


def test_lookups_for_reports_hides_unauthorized_teams(client, session):
    team_a, team_b, leader, _ = _seed_member_and_leader(session)
    headers = login(client, "anurag@prosohm.com")

    reports_teams = client.get("/api/v1/lookups/teams?for_reports=true", headers=headers)
    assert reports_teams.status_code == 200, reports_teams.text
    ids = {row["id"] for row in reports_teams.json()}
    assert str(team_a.id) in ids
    assert str(team_b.id) not in ids


def test_member_timesheet_preview_only_self(client, session):
    """Design Leader who is only a member must not see teammates in timesheet report."""
    team_a, _, leader, member = _seed_member_and_leader(session)

    # Give member Design Leader role so they can hit /reports (require_roles).
    from app.models.models import Role
    from sqlalchemy import select

    dl = session.scalar(select(Role).where(Role.name == "Design Leader"))
    assert dl is not None
    member.role_id = dl.id
    # Ensure member is not treated as team lead
    session.query(TeamMember).filter(
        TeamMember.user_id == member.id,
        TeamMember.relationship_type == TeamRelationshipType.team_leader,
    ).delete()
    session.commit()

    week_start = date(2026, 7, 6)
    for uid, hours in ((member.id, "4"), (leader.id, "8")):
        ts = Timesheet(user_id=uid, week_start=week_start, status=TimesheetStatus.approved)
        session.add(ts)
        session.flush()
        session.add(
            TimesheetEntry(
                timesheet_id=ts.id,
                entry_date=week_start,
                hours=Decimal(hours),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
                description="Report subject clip",
            )
        )
    session.commit()

    headers = login(client, member.email)
    response = client.get(
        "/api/v1/reports/engine/weekly-timesheet/preview",
        headers=headers,
        params={
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
            "team_id": str(team_a.id),
        },
    )
    # Team filter forbidden for own-only when team is membership — should succeed for own team
    # membership, but roster must be self only.
    assert response.status_code == 200, response.text
    designers = response.json().get("designers") or []
    designer_ids = {row["user_id"] for row in designers}
    assert str(leader.id) not in designer_ids
    if designers:
        assert designer_ids <= {str(member.id)}
