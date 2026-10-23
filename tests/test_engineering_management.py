"""Engineering management upgrade: templates, stage hours, baselines, estimates."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.enums import (
    PLANNED_STAGES,
    ExecutionStatus,
    ProjectStage,
    TimesheetStatus,
    WorkCategory,
)
from app.models.models import (
    Customer,
    Milestone,
    Project,
    ProjectEstimateRevision,
    ProjectStageEstimate,
    ProjectTemplate,
    ProjectType,
    Timesheet,
    TimesheetEntry,
)
from tests.conftest import IDS, login


def _next_monday() -> date:
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) or 7)


def _mold_type(session) -> ProjectType:
    row = session.scalar(select(ProjectType).where(ProjectType.name == "Mold Design"))
    assert row is not None
    return row


def _active_template(session, name: str) -> ProjectTemplate:
    rows = session.scalars(select(ProjectTemplate).where(ProjectTemplate.name == name)).all()
    active = [row for row in rows if row.is_active]
    assert active, f"no active template {name}"
    return max(active, key=lambda row: row.version or 1)


def _project_payload(session, *, template_id=None, **extra) -> dict:
    payload = {
        "tool_number": f"T-{uuid.uuid4().hex[:6]}",
        "part_description": "Engineering management part",
        "project_classification": "full_design",
        "customer_id": str(IDS["customer"]),
        "customer_contact_id": str(IDS["contact"]),
        "design_leader_id": str(IDS["user_anurag"]),
        "designer_id": str(IDS["user_binil"]),
        "stream_id": str(IDS["stream"]),
        "project_type_id": str(_mold_type(session).id),
        "project_template_id": str(template_id) if template_id else None,
        "code": f"EM-{uuid.uuid4().hex[:6]}",
    }
    payload.update(extra)
    return payload


def _create_redoe_project(client, session, *, hours=(40, 30, 20), start=None) -> dict:
    template = _active_template(session, "Redoe Mold Design")
    start = start or _next_monday()
    response = client.post(
        "/api/v1/projects",
        json=_project_payload(
            session,
            template_id=template.id,
            start_date=start.isoformat(),
            stage_hours={
                "preliminary": str(hours[0]),
                "intermediate": str(hours[1]),
                "final": str(hours[2]),
            },
        ),
        headers=client.auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ----------------------------------------------------------------- A: templates


def test_template_add_remove_reorder_persists_after_reload(client, session):
    mold = _mold_type(session)
    created = client.post(
        "/api/v1/project-templates",
        json={
            "name": f"Editor Test {uuid.uuid4().hex[:4]}",
            "project_type_id": str(mold.id),
            "scheduling_mode": "dependencies",
            "milestones": [
                {"client_key": "a", "milestone_name": "Blockout", "sort_order": 1,
                 "project_stage": "preliminary", "estimated_hours": "10"},
                {"client_key": "b", "milestone_name": "Intermediate", "sort_order": 2,
                 "project_stage": "intermediate", "depends_on": ["a"]},
                {"client_key": "c", "milestone_name": "Final", "sort_order": 3,
                 "project_stage": "final", "is_required": False, "depends_on": ["b"]},
            ],
        },
        headers=client.auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    by_name = {row["milestone_name"]: row for row in body["milestones"]}
    assert by_name["Intermediate"]["depends_on"] == [by_name["Blockout"]["id"]]
    assert by_name["Final"]["is_required"] is False
    assert body["version"] == 1

    # Reorder, remove "Intermediate", add "Review" depending on Blockout.
    patched = client.patch(
        f"/api/v1/project-templates/{body['id']}",
        json={
            "milestones": [
                {"id": by_name["Final"]["id"], "milestone_name": "Final", "sort_order": 1,
                 "project_stage": "final", "depends_on": []},
                {"id": by_name["Blockout"]["id"], "milestone_name": "Blockout", "sort_order": 2,
                 "project_stage": "preliminary", "estimated_hours": "12"},
                {"client_key": "new", "milestone_name": "Review", "sort_order": 3,
                 "project_stage": "intermediate", "depends_on": [by_name["Blockout"]["id"]]},
            ]
        },
        headers=client.auth_headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["created_new_version"] is False

    reloaded = client.get(f"/api/v1/project-templates/{body['id']}", headers=client.auth_headers)
    assert reloaded.status_code == 200
    rows = reloaded.json()["milestones"]
    assert [row["milestone_name"] for row in rows] == ["Final", "Blockout", "Review"]
    assert rows[1]["estimated_hours"] in ("12.00", "12")
    assert rows[1]["id"] == by_name["Blockout"]["id"]
    assert rows[2]["depends_on"] == [by_name["Blockout"]["id"]]
    assert rows[2]["project_stage"] == "intermediate"


def test_template_dependency_cycle_and_duplicates_rejected(client, session):
    mold = _mold_type(session)
    cycle = client.post(
        "/api/v1/project-templates",
        json={
            "name": f"Cycle {uuid.uuid4().hex[:4]}",
            "project_type_id": str(mold.id),
            "scheduling_mode": "dependencies",
            "milestones": [
                {"client_key": "a", "milestone_name": "A", "depends_on": ["b"]},
                {"client_key": "b", "milestone_name": "B", "depends_on": ["a"]},
            ],
        },
        headers=client.auth_headers,
    )
    assert cycle.status_code == 422, cycle.text
    duplicate = client.post(
        "/api/v1/project-templates",
        json={
            "name": f"Dup {uuid.uuid4().hex[:4]}",
            "project_type_id": str(mold.id),
            "milestones": [{"milestone_name": "A"}, {"milestone_name": "a "}],
        },
        headers=client.auth_headers,
    )
    assert duplicate.status_code == 422, duplicate.text


def test_editing_template_in_use_creates_version_and_keeps_existing_projects(client, session):
    project = _create_redoe_project(client, session)
    template_id = project["project_template_id"]
    before = [
        row.name
        for row in session.scalars(
            select(Milestone)
            .where(Milestone.project_id == uuid.UUID(project["id"]))
            .order_by(Milestone.sort_order)
        )
    ]

    response = client.patch(
        f"/api/v1/project-templates/{template_id}",
        json={
            "milestones": [
                {"milestone_name": "Blockout", "sort_order": 1, "project_stage": "preliminary"},
                {"milestone_name": "Intermediate Review", "sort_order": 2,
                 "project_stage": "intermediate"},
                {"milestone_name": "Final Review", "sort_order": 3, "project_stage": "final"},
            ]
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created_new_version"] is True
    assert body["version"] == 2
    assert body["id"] != template_id

    session.expire_all()
    after = [
        row.name
        for row in session.scalars(
            select(Milestone)
            .where(Milestone.project_id == uuid.UUID(project["id"]))
            .order_by(Milestone.sort_order)
        )
    ]
    assert after == before
    old = session.get(ProjectTemplate, uuid.UUID(template_id))
    assert old is not None and old.is_active is False

    versions = client.get(
        f"/api/v1/project-templates/{body['id']}/versions", headers=client.auth_headers
    )
    assert versions.status_code == 200
    assert [row["version"] for row in versions.json()] == [2, 1]

    # A new project picked with the old id resolves to the active version.
    second = _create_redoe_project(client, session)
    names = [
        row.name
        for row in session.scalars(
            select(Milestone)
            .where(Milestone.project_id == uuid.UUID(second["id"]))
            .order_by(Milestone.sort_order)
        )
    ]
    assert names == ["Blockout", "Intermediate Review", "Final Review"]


def test_template_preview_schedules_without_saving(client, session):
    template = _active_template(session, "Redoe Mold Design")
    count_before = session.scalar(select(Project.id).limit(1))
    response = client.post(
        f"/api/v1/project-templates/{template.id}/preview",
        json={
            "start_date": _next_monday().isoformat(),
            "stage_hours": {"preliminary": "16", "intermediate": "8", "final": "24"},
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["forecast_status"] == "provisional"
    assert "Provisional forecast" in body["forecast_note"]
    total = sum(Decimal(row["planned_hours"]) for row in body["milestones"])
    assert total == Decimal("48")
    assert body["completion_date"] is not None
    assert session.scalar(select(Project.id).limit(1)) == count_before


def test_crest_and_redoe_templates_use_three_stages(session):
    for name in ("Crest Mold Technologies Template", "Redoe Mold Design"):
        template = _active_template(session, name)
        stages = {row.project_stage for row in template.milestones}
        assert stages == set(PLANNED_STAGES), name


def test_non_manager_cannot_edit_templates(client, session):
    template = _active_template(session, "Redoe Mold Design")
    headers = login(client, "binil@prosohm.com")
    response = client.patch(
        f"/api/v1/project-templates/{template.id}",
        json={"description": "x"},
        headers=headers,
    )
    assert response.status_code == 403


# ----------------------------------------------------- B: start date + stage hours


def test_create_project_with_start_date_and_stage_hours(client, session):
    start = _next_monday()
    project = _create_redoe_project(client, session, hours=(40, 30, 20), start=start)
    assert Decimal(project["quoted_hours"]) == Decimal("90")
    assert project["start_date"] == start.isoformat()
    assert project["stage_estimates_configured"] is True
    assert project["baseline_version"] == 1
    assert project["baseline_start_date"] == start.isoformat()
    assert project["baseline_completion_date"] is not None
    assert project["forecast_status"] == "provisional"
    assert project["actual_start_date"] is None
    assert project["actual_completion_date"] is None

    project_id = uuid.UUID(project["id"])
    estimates = {
        row.stage: row
        for row in session.scalars(
            select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == project_id)
        )
    }
    assert estimates[ProjectStage.preliminary].original_hours == Decimal("40")
    assert estimates[ProjectStage.preliminary].current_hours == Decimal("40")
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    ).all()
    per_stage: dict[ProjectStage, Decimal] = {}
    for row in milestones:
        per_stage[row.project_stage] = per_stage.get(row.project_stage, Decimal("0")) + row.planned_hours
        assert row.original_planned_hours == row.planned_hours
        assert row.baseline_finish_date is not None
        assert row.baseline_finish_date.weekday() < 5
    assert per_stage == {
        ProjectStage.preliminary: Decimal("40"),
        ProjectStage.intermediate: Decimal("30"),
        ProjectStage.final: Decimal("20"),
    }
    assert project["baseline_completion_date"] == max(
        row.baseline_finish_date for row in milestones
    ).isoformat()


def test_stage_hours_validation(client, session):
    template = _active_template(session, "Redoe Mold Design")
    negative = client.post(
        "/api/v1/projects",
        json=_project_payload(
            session,
            template_id=template.id,
            stage_hours={"preliminary": "-1", "intermediate": "0", "final": "0"},
        ),
        headers=client.auth_headers,
    )
    assert negative.status_code == 422
    mismatch = client.post(
        "/api/v1/projects",
        json=_project_payload(
            session,
            template_id=template.id,
            quoted_hours="100",
            stage_hours={"preliminary": "10", "intermediate": "10", "final": "10"},
        ),
        headers=client.auth_headers,
    )
    assert mismatch.status_code == 422


def test_project_without_start_date_has_no_invented_dates(client, session):
    template = _active_template(session, "Redoe Mold Design")
    response = client.post(
        "/api/v1/projects",
        json=_project_payload(
            session,
            template_id=template.id,
            stage_hours={"preliminary": "10", "intermediate": "10", "final": "10"},
        ),
        headers=client.auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["start_date"] is None
    assert body["baseline_completion_date"] is None
    assert body["baseline_version"] == 0
    assert body["forecast_status"] == "unconfigured"


# ------------------------------------------------- C: estimates, actuals, baseline


def test_estimate_revision_keeps_original_and_records_audit(client, session):
    project = _create_redoe_project(client, session)
    url = f"/api/v1/projects/{project['id']}/stage-estimates/revisions"

    missing_reason = client.post(
        url,
        json={"stage": "preliminary", "new_hours": "50", "reason": ""},
        headers=client.auth_headers,
    )
    assert missing_reason.status_code == 422

    designer = login(client, "binil@prosohm.com")
    forbidden = client.post(
        url,
        json={"stage": "preliminary", "new_hours": "50", "reason": "Customer added ribs"},
        headers=designer,
    )
    assert forbidden.status_code == 403

    response = client.post(
        url,
        json={"stage": "preliminary", "new_hours": "50", "reason": "Customer added ribs"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    blockout = next(stage for stage in plan["stages"] if stage["key"] == "preliminary")
    assert Decimal(blockout["original_hours"]) == Decimal("40")
    assert Decimal(blockout["current_hours"]) == Decimal("50")
    assert Decimal(blockout["milestone_planned_hours"]) == Decimal("50")
    assert blockout["allocation_mismatch"] is False
    assert Decimal(plan["original_total_hours"]) == Decimal("90")
    assert Decimal(plan["current_total_hours"]) == Decimal("100")
    assert plan["estimate_revisions"][0]["reason"] == "Customer added ribs"
    assert plan["estimate_revisions"][0]["revised_by_name"]

    session.expire_all()
    revisions = session.scalars(
        select(ProjectEstimateRevision).where(
            ProjectEstimateRevision.project_id == uuid.UUID(project["id"])
        )
    ).all()
    assert len(revisions) == 1
    assert revisions[0].previous_hours == Decimal("40")
    stored = session.get(Project, uuid.UUID(project["id"]))
    assert stored is not None and stored.quoted_hours == Decimal("90")


def test_stage_plan_actual_hours_come_from_timesheets(client, session):
    project = _create_redoe_project(client, session)
    project_id = uuid.UUID(project["id"])
    blockout = session.scalar(
        select(Milestone).where(Milestone.project_id == project_id, Milestone.name == "Blockout")
    )
    assert blockout is not None
    week_start = date.today() - timedelta(days=date.today().weekday())
    sheet = Timesheet(
        id=uuid.uuid4(),
        user_id=IDS["user_binil"],
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(sheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=sheet.id,
            entry_date=week_start,
            hours=Decimal("6"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=project_id,
            milestone_id=blockout.id,
        )
    )
    session.commit()

    response = client.get(f"/api/v1/projects/{project_id}/stage-plan", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    plan = response.json()
    stage = next(row for row in plan["stages"] if row["key"] == "preliminary")
    assert Decimal(stage["actual_hours"]) == Decimal("6")
    line = next(row for row in stage["milestones"] if row["name"] == "Blockout")
    assert Decimal(line["actual_hours"]) == Decimal("6")
    assert Decimal(line["forecast_remaining_hours"]) == Decimal(line["planned_hours"]) - Decimal("6")
    assert plan["actual_start_date"] == week_start.isoformat()
    assert Decimal(plan["actual_total_hours"]) == Decimal("6")


def test_baseline_revision_keeps_history(client, session):
    project = _create_redoe_project(client, session)
    url = f"/api/v1/projects/{project['id']}/baseline-revisions"
    designer = login(client, "anurag@prosohm.com")
    forbidden = client.post(
        url, json={"reason": "Customer delayed data"}, headers=designer
    )
    assert forbidden.status_code == 403

    new_start = _next_monday() + timedelta(days=14)
    response = client.post(
        url,
        json={"reason": "Customer delayed data", "new_start_date": new_start.isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["baseline_version"] == 2
    assert plan["start_date"] == new_start.isoformat()
    assert plan["baseline_start_date"] == new_start.isoformat()
    numbers = [row["revision_number"] for row in plan["baseline_revisions"]]
    assert numbers == [2, 1]
    latest = plan["baseline_revisions"][0]
    assert latest["previous_completion_date"] == project["baseline_completion_date"]
    assert latest["reason"] == "Customer delayed data"


def test_schedule_override_requires_reason_and_is_used(client, session):
    project = _create_redoe_project(client, session)
    project_id = uuid.UUID(project["id"])
    final = session.scalar(
        select(Milestone).where(Milestone.project_id == project_id, Milestone.name == "BOM Release")
    )
    assert final is not None
    url = f"/api/v1/projects/{project_id}/milestones/{final.id}/schedule-override"
    target = _next_monday() + timedelta(days=70)
    no_reason = client.put(
        url, json={"override_finish_date": target.isoformat()}, headers=client.auth_headers
    )
    assert no_reason.status_code == 422
    response = client.put(
        url,
        json={"override_finish_date": target.isoformat(), "reason": "Customer fixed date"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["forecast_completion_date"] == target.isoformat()


# ------------------------------------------------------ end customer + completion


def test_end_customer_is_optional_and_validated(client, session):
    end_customer = Customer(name=f"End OEM {uuid.uuid4().hex[:4]}", code=uuid.uuid4().hex[:6], is_active=True)
    session.add(end_customer)
    session.commit()
    response = client.post(
        "/api/v1/projects",
        json=_project_payload(session, end_customer_id=str(end_customer.id)),
        headers=client.auth_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["end_customer_name"] == end_customer.name

    unknown = client.post(
        "/api/v1/projects",
        json=_project_payload(session, end_customer_id=str(uuid.uuid4())),
        headers=client.auth_headers,
    )
    assert unknown.status_code == 422


def test_actual_completion_date_and_reopen_permission(client, session):
    from app.models.enums import MilestoneStatus

    project_id = IDS["project"]
    for row in session.scalars(select(Milestone).where(Milestone.project_id == project_id)):
        row.status = MilestoneStatus.completed
        row.completed_date = date.today() - timedelta(days=3)
    session.commit()
    future = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "completed", "actual_completion_date": (date.today() + timedelta(days=3)).isoformat()},
        headers=client.auth_headers,
    )
    assert future.status_code == 422

    done_on = date.today() - timedelta(days=2)
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "completed", "actual_completion_date": done_on.isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["actual_completion_date"] == done_on.isoformat()

    leader = login(client, "anurag@prosohm.com")
    reopen = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "currently_being_worked_on"},
        headers=leader,
    )
    assert reopen.status_code == 403

    admin_reopen = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "currently_being_worked_on"},
        headers=client.auth_headers,
    )
    assert admin_reopen.status_code == 200
    session.expire_all()
    stored = session.get(Project, project_id)
    assert stored is not None
    assert stored.execution_status == ExecutionStatus.currently_being_worked_on
    assert stored.completed_at is None
