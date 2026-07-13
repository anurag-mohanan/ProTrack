"""Tests for per-team timesheet report inclusion flag."""

from datetime import date
from decimal import Decimal
import uuid

from app.models.enums import TeamRelationshipType, TimesheetStatus, WorkCategory
from app.models.models import Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.customer_timesheet_pack import build_customer_timesheet_pack
from app.services.reporting.data_service import build_engineering_report
from app.services.reporting.report_scope import ReportScope
from tests.conftest import IDS


def _seed_excluded_designer(session):
    team = Team(id=uuid.uuid4(), name="Exclude Reports Team", is_active=True)
    session.add(team)
    session.flush()

    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = team.id
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            relationship_type=TeamRelationshipType.member,
            is_primary=True,
            include_in_timesheet_reports=False,
        )
    )

    week_start = date(2026, 6, 8)
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
        )
    )
    session.commit()
    return team, week_start


def test_excluded_team_member_omitted_from_engineering_report(session):
    team, week_start = _seed_excluded_designer(session)
    payload = build_engineering_report(
        session,
        period_type="weekly",
        anchor=week_start,
        scope=ReportScope(
            team_ids=frozenset({team.id}),
            user_ids=frozenset({IDS["user_binil"]}),
        ),
    )
    designer_ids = {row.user_id for row in payload.designer_productivity}
    assert IDS["user_binil"] not in designer_ids


def test_excluded_member_omitted_from_customer_pack(session):
    team, week_start = _seed_excluded_designer(session)
    admin = session.get(User, IDS["user_admin"])
    pack = build_customer_timesheet_pack(
        session,
        customer_id=IDS["customer"],
        current_user=admin,
        period_type="weekly",
        anchor=week_start,
        team_id=team.id,
    )
    assert pack.associates == []
