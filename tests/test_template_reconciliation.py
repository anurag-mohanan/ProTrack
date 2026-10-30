"""Smart template change: acceptance scenarios 1-10 plus safety checks.

Every scenario goes through the real preview/apply endpoints (or the service for
failure injection) and asserts that completed work, completion dates, timesheet
links and history survive, and that merged/superseded/archived records stop
counting in progress.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.project_template_seed import ensure_project_types_and_templates
from app.models.enums import ActivityAction, MilestoneStatus, ProjectStage, TimesheetStatus, WorkCategory
from app.models.models import (
    Activity,
    Milestone,
    Project,
    ProjectTemplate,
    ProjectTemplateMilestone,
    ProjectType,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.models.workflow import ProjectTemplateReconciliation
from app.services.project_calculation_service import calculate_progress
from app.services.scheduling_service import dump_id_list, parse_id_list
from tests.conftest import IDS, login
from tests.test_project_templates import _create_project_payload


@pytest.fixture
def template_db(session):
    ensure_project_types_and_templates(session)
    return session


def _mold(session) -> ProjectType:
    return session.scalar(select(ProjectType).where(ProjectType.name == "Mold Design"))


def _template_by_name(session, name: str) -> ProjectTemplate:
    return session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == name))


def _template(session, name: str, rows: list[dict]) -> ProjectTemplate:
    template = ProjectTemplate(name=name, project_type_id=_mold(session).id, is_active=True, version=1)
    session.add(template)
    session.flush()
    template.template_family_id = template.id
    by_name: dict[str, ProjectTemplateMilestone] = {}
    for index, row in enumerate(rows, start=1):
        item = ProjectTemplateMilestone(
            project_template_id=template.id,
            milestone_name=row["name"],
            sort_order=index,
            project_stage=row.get("stage"),
            is_required=row.get("required", True),
            default_due_offset_days=row.get("offset"),
            estimated_hours=row.get("hours"),
            assigned_role=row.get("role"),
        )
        session.add(item)
        session.flush()
        item.lineage_id = item.id
        by_name[row["name"]] = item
    for row in rows:
        if row.get("deps"):
            by_name[row["name"]].depends_on_ids = dump_id_list([by_name[d].id for d in row["deps"]])
    session.commit()
    return template


def _new_project(client, session, template: ProjectTemplate) -> uuid.UUID:
    payload = _create_project_payload(
        session,
        customer_id=IDS["customer"],
        contact_id=IDS["contact"],
        project_type_id=_mold(session).id,
        template_id=template.id,
    )
    response = client.post("/api/v1/projects", json=payload, headers=client.auth_headers)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def _get(session, model, record_id):
    session.expire_all()
    return session.get(model, record_id)


def _milestones(session, project_id, *, active_only: bool = False) -> list[Milestone]:
    session.expire_all()
    stmt = select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    if active_only:
        stmt = stmt.where(Milestone.lifecycle_state == "active")
    return list(session.scalars(stmt).all())


def _by_name(session, project_id, name: str) -> Milestone:
    rows = [m for m in _milestones(session, project_id) if m.name == name]
    assert len(rows) == 1, f"expected one '{name}', got {len(rows)}"
    return rows[0]


def _complete(session, milestone: Milestone, on: date) -> None:
    milestone.status = MilestoneStatus.completed
    milestone.completed_date = on
    milestone.progress_percent = 100
    session.commit()


def _book(session, project_id, milestone_id, hours: str) -> TimesheetEntry:
    sheet = Timesheet(
        user_id=IDS["user_binil"],
        week_start=date(2026, 1, 5) + timedelta(weeks=len(session.scalars(select(Timesheet)).all())),
        status=TimesheetStatus.approved,
    )
    session.add(sheet)
    session.flush()
    entry = TimesheetEntry(
        timesheet_id=sheet.id,
        entry_date=sheet.week_start,
        hours=Decimal(hours),
        work_category=WorkCategory.productive,
        is_billable=True,
        customer_id=IDS["customer"],
        project_id=project_id,
        milestone_id=milestone_id,
    )
    session.add(entry)
    session.commit()
    return entry


def _preview(client, project_id, template_id, headers=None, **body):
    response = client.post(
        f"/api/v1/projects/{project_id}/template-reconciliation/preview",
        json={"template_id": str(template_id), **body},
        headers=headers or client.auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client, project_id, preview, *, key: str | None = None, expect: int = 200, **body):
    payload = {
        "template_id": preview["new_template"]["id"],
        "preview_fingerprint": preview["fingerprint"],
        "plan_version": preview["plan_version"],
        "request_key": key or uuid.uuid4().hex,
        "confirm": True,
        **body,
    }
    response = client.post(
        f"/api/v1/projects/{project_id}/template-reconciliation/apply",
        json=payload,
        headers=client.auth_headers,
    )
    assert response.status_code == expect, response.text
    return response.json()


def _snapshot(session, project_id) -> list[tuple]:
    return [
        (m.id, m.name, m.status, m.lifecycle_state, m.completed_date, m.depends_on_ids, m.sort_order,
         m.template_milestone_id, m.updated_at)
        for m in _milestones(session, project_id)
    ]


BLOCKOUT_ONLY = [{"name": "Blockout", "stage": ProjectStage.preliminary}]


# --------------------------------------------------------------------------- scenario 1


def test_scenario1_blockout_only_to_full_template(client, template_db):
    session = template_db
    blockout_only = _template(session, "Blockout Only", BLOCKOUT_ONLY)
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, blockout_only)
    blockout = _by_name(session, project_id, "Blockout")
    _complete(session, blockout, date(2026, 2, 3))
    entry = _book(session, project_id, blockout.id, "6")

    preview = _preview(client, project_id, general.id)
    assert preview["counts"]["match"] == 1
    assert preview["counts"]["add"] == 6
    assert preview["counts"]["merge"] == preview["counts"]["supersede"] == preview["counts"]["archive"] == 0
    blockout_row = next(m for m in preview["matches"] if m["template_name"] == "Blockout")
    assert blockout_row["classification"] == "confirmed"
    assert blockout_row["completion_retained"] is True
    assert blockout_row["milestone"]["id"] == str(blockout.id)

    result = _apply(client, project_id, preview, reason="Customer moved to the full mold design scope")
    assert result["replayed"] is False
    assert result["reconciliation"]["counts"]["add"] == 6

    kept = _get(session, Milestone, blockout.id)
    assert kept.status == MilestoneStatus.completed
    assert kept.completed_date == date(2026, 2, 3)
    general_blockout = next(m for m in general.milestones if m.milestone_name == "Blockout")
    assert kept.template_milestone_id == general_blockout.id
    assert _get(session, TimesheetEntry, entry.id).milestone_id == blockout.id

    active = _milestones(session, project_id, active_only=True)
    assert [m.name for m in active] == [
        "Feasibility", "Blockout", "Roughing", "Intermediate Review", "Final Review", "File Release", "BOM Release",
    ]
    added = [m for m in active if m.id != blockout.id]
    assert all(m.status == MilestoneStatus.not_started and m.reconciliation_id for m in added)
    assert all(m.template_milestone_id in {t.id for t in general.milestones} for m in added)
    assert all(m.planned_hours == 0 for m in added), "template hours are applied only on request"

    project = _get(session, Project, project_id)
    assert project.project_template_id == general.id
    assert project.milestone_plan_version == 1
    progress = calculate_progress(session, project)
    assert (progress.completed_milestones, progress.total_milestones) == (1, 7)

    recon = session.scalar(select(ProjectTemplateReconciliation).where(ProjectTemplateReconciliation.project_id == project_id))
    assert recon.status == "applied"
    assert recon.previous_template_id == blockout_only.id and recon.new_template_id == general.id
    assert recon.reason == "Customer moved to the full mold design scope"
    activity = session.scalar(
        select(Activity).where(
            Activity.entity_id == project_id, Activity.action == ActivityAction.project_template_reconciled
        )
    )
    assert activity is not None and activity.user_id == IDS["user_admin"]


# --------------------------------------------------------------------------- scenario 2


def test_scenario2_change_with_pending_milestones(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    sybridge = _template_by_name(session, "Sybridge Mold Design")
    project_id = _new_project(client, session, general)
    before_ids = {m.id for m in _milestones(session, project_id)}

    preview = _preview(client, project_id, sybridge.id)
    decisions = {m["template_name"]: m for m in preview["matches"]}
    assert decisions["Customer Intermediate Review"]["decision"] == "add"
    assert all(c["classification"] != "confirmed" for c in decisions["Customer Intermediate Review"]["candidates"])
    not_in_template = {row["name"] for row in preview["not_in_template"]}
    assert {"Roughing", "Intermediate Review"} <= not_in_template
    assert all(row["decision"] == "retain" for row in preview["not_in_template"])

    roughing = _by_name(session, project_id, "Roughing")
    supersede = [{"milestone_id": str(roughing.id), "action": "supersede"}]
    preview = _preview(client, project_id, sybridge.id, existing_decisions=supersede)
    _apply(client, project_id, preview, existing_decisions=supersede)

    after = _milestones(session, project_id)
    assert before_ids <= {m.id for m in after}, "no existing milestone was deleted"
    superseded = _get(session, Milestone, roughing.id)
    assert superseded.lifecycle_state == "superseded"
    assert superseded.status == MilestoneStatus.not_started, "workflow status is not rewritten"
    active_names = [m.name for m in _milestones(session, project_id, active_only=True)]
    assert "Roughing" not in active_names
    assert "Customer Intermediate Review" in active_names and "Intermediate Review" in active_names
    progress = calculate_progress(session, _get(session, Project, project_id))
    assert progress.total_milestones == len(active_names)

    listed = client.get(f"/api/v1/milestones?project_id={project_id}", headers=client.auth_headers).json()
    assert str(roughing.id) not in {row["id"] for row in listed}
    history = client.get(
        f"/api/v1/milestones?project_id={project_id}&include_inactive=true", headers=client.auth_headers
    ).json()
    row = next(r for r in history if r["id"] == str(roughing.id))
    assert row["lifecycle_state"] == "superseded"


# --------------------------------------------------------------------------- scenario 3


def test_scenario3_similar_names_are_not_matched_or_merged(client, template_db):
    session = template_db
    source = _template(session, "Flow Source", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Mold Flow Report", "stage": ProjectStage.intermediate},
        {"name": "Intermediate Review", "stage": ProjectStage.intermediate},
    ])
    target = _template(session, "Flow Target", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Mold Flow Analysis", "stage": ProjectStage.intermediate},
        {"name": "Intermediate Design Review", "stage": ProjectStage.intermediate},
    ])
    project_id = _new_project(client, session, source)

    preview = _preview(client, project_id, target.id)
    rows = {m["template_name"]: m for m in preview["matches"]}
    for name, existing in (("Mold Flow Analysis", "Mold Flow Report"), ("Intermediate Design Review", "Intermediate Review")):
        assert rows[name]["decision"] == "add"
        assert rows[name]["needs_review"] is True
        candidate = next(c for c in rows[name]["candidates"] if c["milestone_name"] == existing)
        assert candidate["classification"] == "possible"
        assert candidate["requires_confirmation"] is True
    assert preview["counts"]["merge"] == 0

    _apply(client, project_id, preview)
    names = sorted(m.name for m in _milestones(session, project_id, active_only=True))
    assert names == sorted([
        "Blockout", "Mold Flow Report", "Intermediate Review", "Mold Flow Analysis", "Intermediate Design Review",
    ])

    # The user may explicitly confirm a possible match.
    other = _new_project(client, session, source)
    flow = _by_name(session, other, "Mold Flow Report")
    item = next(t for t in target.milestones if t.milestone_name == "Mold Flow Analysis")
    choice = [{"template_milestone_id": str(item.id), "action": "match", "milestone_id": str(flow.id)}]
    preview = _preview(client, other, target.id, template_decisions=choice)
    _apply(client, other, preview, template_decisions=choice)
    assert _get(session, Milestone, flow.id).template_milestone_id == item.id
    assert [m.name for m in _milestones(session, other) if m.name.startswith("Mold Flow")] == ["Mold Flow Report"]


# --------------------------------------------------------------------------- scenario 4


def _duplicate_of(session, original: Milestone, **overrides) -> Milestone:
    copy = Milestone(
        project_id=original.project_id,
        name=original.name,
        status=overrides.get("status", original.status),
        completed_date=overrides.get("completed_date", original.completed_date),
        progress_percent=overrides.get("progress_percent", original.progress_percent),
        project_stage=original.project_stage,
        template_milestone_id=original.template_milestone_id,
        is_required=original.is_required,
        sort_order=original.sort_order,
        assigned_user_id=overrides.get("assigned_user_id", original.assigned_user_id),
    )
    session.add(copy)
    session.commit()
    return copy


def test_scenario4_two_completed_duplicates_merge_into_one(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    first = _by_name(session, project_id, "Blockout")
    _complete(session, first, date(2026, 3, 1))
    second = _duplicate_of(session, first, completed_date=date(2026, 3, 9))
    roughing = _by_name(session, project_id, "Roughing")
    roughing.depends_on_ids = dump_id_list([second.id])
    session.commit()
    _book(session, project_id, first.id, "5")
    second_entry = _book(session, project_id, second.id, "3")
    total_hours_before = session.scalar(
        select(func.sum(TimesheetEntry.hours)).where(TimesheetEntry.project_id == project_id)
    )

    preview = _preview(client, project_id, general.id)
    dup = next(d for d in preview["duplicates"] if d["milestone"]["id"] == str(second.id))
    assert dup["classification"] == "confirmed"
    assert dup["default_action"] == "merge"
    assert dup["canonical"]["id"] == str(first.id), "earliest completion is the surviving record"
    assert preview["counts"]["merge"] == 1

    _apply(client, project_id, preview)
    merged, canonical = _get(session, Milestone, second.id), _get(session, Milestone, first.id)
    assert merged.lifecycle_state == "merged" and merged.merged_into_id == first.id
    assert merged.status == MilestoneStatus.completed and merged.completed_date == date(2026, 3, 9)
    assert canonical.status == MilestoneStatus.completed and canonical.completed_date == date(2026, 3, 1)
    assert _get(session, TimesheetEntry, second_entry.id).milestone_id == second.id
    assert session.scalar(
        select(func.sum(TimesheetEntry.hours)).where(TimesheetEntry.project_id == project_id)
    ) == total_hours_before
    assert str(first.id) in parse_id_list(_get(session, Milestone, roughing.id).depends_on_ids)
    assert str(second.id) not in parse_id_list(_get(session, Milestone, roughing.id).depends_on_ids)
    progress = calculate_progress(session, _get(session, Project, project_id))
    assert (progress.completed_milestones, progress.total_milestones) == (1, 7), "no double count"

    recon = session.scalar(select(ProjectTemplateReconciliation).where(ProjectTemplateReconciliation.project_id == project_id))
    assert recon.merged_count == 1
    assert '"canonical_completed_date": "2026-03-01"' in recon.decisions_json
    assert '"merged_completed_date": "2026-03-09"' in recon.decisions_json

    response = client.patch(f"/api/v1/milestones/{second.id}", json={"status": "in_progress"}, headers=client.auth_headers)
    assert response.status_code == 409
    response = client.delete(f"/api/v1/milestones/{first.id}", headers=client.auth_headers)
    assert response.status_code == 409


# --------------------------------------------------------------------------- scenario 5


def test_scenario5_completed_and_pending_duplicate(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    done = _by_name(session, project_id, "Blockout")
    _complete(session, done, date(2026, 4, 2))
    pending = _duplicate_of(
        session, done, status=MilestoneStatus.not_started, completed_date=None, progress_percent=0,
        assigned_user_id=None,
    )

    preview = _preview(client, project_id, general.id)
    dup = next(d for d in preview["duplicates"] if str(pending.id) in {d["milestone"]["id"], d["canonical"]["id"]})
    assert dup["classification"] == "likely"
    assert dup["default_action"] == "retain", "likely duplicates need the user's confirmation"
    assert dup["canonical"]["id"] == str(done.id)

    wrong_way = [{"milestone_id": str(done.id), "action": "merge", "merge_into_id": str(pending.id)}]
    response = client.post(
        f"/api/v1/projects/{project_id}/template-reconciliation/preview",
        json={"template_id": str(general.id), "existing_decisions": wrong_way},
        headers=client.auth_headers,
    )
    assert response.status_code == 422
    assert "matches the new template" in response.json()["detail"] or "completed" in response.json()["detail"]

    merge = [{"milestone_id": str(pending.id), "action": "merge", "merge_into_id": str(done.id)}]
    preview = _preview(client, project_id, general.id, existing_decisions=merge)
    _apply(client, project_id, preview, existing_decisions=merge)
    assert _get(session, Milestone, done.id).status == MilestoneStatus.completed
    assert _get(session, Milestone, done.id).completed_date == date(2026, 4, 2)
    assert _get(session, Milestone, pending.id).lifecycle_state == "merged"
    assert _get(session, Milestone, pending.id).status == MilestoneStatus.not_started


def test_completed_milestone_is_never_merged_into_incomplete_one(client, template_db):
    session = template_db
    source = _template(session, "Two Pieces", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Extra Check", "stage": ProjectStage.preliminary},
    ])
    project_id = _new_project(client, session, source)
    extra = _by_name(session, project_id, "Extra Check")
    _complete(session, extra, date(2026, 4, 3))
    blockout = _by_name(session, project_id, "Blockout")
    target = _template(session, "Blockout Again", BLOCKOUT_ONLY)
    merge = [{"milestone_id": str(extra.id), "action": "merge", "merge_into_id": str(blockout.id)}]
    response = client.post(
        f"/api/v1/projects/{project_id}/template-reconciliation/preview",
        json={"template_id": str(target.id), "existing_decisions": merge},
        headers=client.auth_headers,
    )
    assert response.status_code == 422
    assert "completion evidence" in response.json()["detail"]


# --------------------------------------------------------------------------- scenario 6


def test_scenario6_downgrade_keeps_everything_until_user_archives(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    blockout_only = _template(session, "Blockout Lite", BLOCKOUT_ONLY)
    project_id = _new_project(client, session, general)
    feasibility = _by_name(session, project_id, "Feasibility")
    _complete(session, feasibility, date(2026, 5, 1))

    preview = _preview(client, project_id, blockout_only.id)
    assert preview["counts"]["match"] == 1 and preview["counts"]["add"] == 0
    assert len(preview["not_in_template"]) == 6
    _apply(client, project_id, preview)
    assert len(_milestones(session, project_id, active_only=True)) == 7, "downgrade never deletes work"

    archive = [
        {"milestone_id": str(m.id), "action": "archive"}
        for m in _milestones(session, project_id, active_only=True)
        if m.name != "Blockout"
    ]
    preview = _preview(client, project_id, blockout_only.id, existing_decisions=archive)
    assert preview["consequential"] is True
    _apply(client, project_id, preview, existing_decisions=archive)
    assert [m.name for m in _milestones(session, project_id, active_only=True)] == ["Blockout"]
    archived = _get(session, Milestone, feasibility.id)
    assert archived.lifecycle_state == "archived"
    assert archived.status == MilestoneStatus.completed and archived.completed_date == date(2026, 5, 1)
    assert len(_milestones(session, project_id)) == 7
    progress = calculate_progress(session, _get(session, Project, project_id))
    assert progress.total_milestones == 1


# --------------------------------------------------------------------------- scenario 7


def test_scenario7_cancelled_and_superseded_are_not_reactivated(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    blockout_only = _template(session, "Blockout Narrow", BLOCKOUT_ONLY)
    project_id = _new_project(client, session, general)
    cancelled = _by_name(session, project_id, "Final Review")
    cancelled.status = MilestoneStatus.cancelled
    session.commit()

    roughing = _by_name(session, project_id, "Roughing")
    supersede = [{"milestone_id": str(roughing.id), "action": "supersede"}]
    preview = _preview(client, project_id, blockout_only.id, existing_decisions=supersede)
    _apply(client, project_id, preview, existing_decisions=supersede)

    preview = _preview(client, project_id, general.id)
    assert str(roughing.id) in {m["id"] for m in preview["inactive_milestones"]}
    assert str(roughing.id) not in {m["id"] for m in preview["existing"]}
    final_row = next(m for m in preview["matches"] if m["template_name"] == "Final Review")
    assert final_row["milestone"]["id"] == str(cancelled.id)
    _apply(client, project_id, preview)

    assert _get(session, Milestone, roughing.id).lifecycle_state == "superseded"
    assert _get(session, Milestone, cancelled.id).status == MilestoneStatus.cancelled
    active_roughing = [m for m in _milestones(session, project_id, active_only=True) if m.name == "Roughing"]
    assert len(active_roughing) == 1 and active_roughing[0].id != roughing.id


# --------------------------------------------------------------------------- scenario 8


def test_scenario8_cancelled_preview_changes_nothing(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    sybridge = _template_by_name(session, "Sybridge Mold Design")
    project_id = _new_project(client, session, general)
    before = _snapshot(session, project_id)
    _preview(client, project_id, sybridge.id)
    _preview(client, project_id, _template(session, "Preview Only", BLOCKOUT_ONLY).id)
    assert _snapshot(session, project_id) == before
    project = _get(session, Project, project_id)
    assert project.project_template_id == general.id
    assert project.milestone_plan_version == 0
    assert session.scalar(select(func.count()).select_from(ProjectTemplateReconciliation)) == 0


def test_apply_requires_explicit_confirmation(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    preview = _preview(client, project_id, _template(session, "Needs Confirm", BLOCKOUT_ONLY).id)
    before = _snapshot(session, project_id)
    _apply(client, project_id, preview, confirm=False, expect=422)
    assert _snapshot(session, project_id) == before


# --------------------------------------------------------------------------- scenario 9


def test_scenario9_failure_rolls_back_and_records_error(client, template_db, monkeypatch):
    from app.services import template_reconciliation as service

    session = template_db
    blockout_only = _template(session, "Blockout Fail", BLOCKOUT_ONLY)
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, blockout_only)
    _complete(session, _by_name(session, project_id, "Blockout"), date(2026, 6, 1))
    before = _snapshot(session, project_id)
    preview = _preview(client, project_id, general.id)

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(service, "_validate_no_cycle", boom)
    request = service.ApplyRequest(
        template_id=general.id,
        fingerprint=preview["fingerprint"],
        plan_version=preview["plan_version"],
        request_key=uuid.uuid4().hex,
        confirm=True,
    )
    with pytest.raises(RuntimeError):
        service.apply(session, project_id, _get(session, User, IDS["user_admin"]), request)

    assert _snapshot(session, project_id) == before
    project = _get(session, Project, project_id)
    assert project.project_template_id == blockout_only.id
    assert project.milestone_plan_version == 0
    failed = session.scalar(select(ProjectTemplateReconciliation).where(ProjectTemplateReconciliation.project_id == project_id))
    assert failed.status == "failed"
    assert "simulated storage failure" in failed.error_message
    history = client.get(f"/api/v1/projects/{project_id}/template-reconciliations", headers=client.auth_headers).json()
    assert history[0]["status"] == "failed"

    monkeypatch.undo()
    retry = _apply(client, project_id, _preview(client, project_id, general.id))
    assert retry["reconciliation"]["status"] == "applied"


# --------------------------------------------------------------------------- scenario 10


def test_scenario10_repeated_application_is_idempotent(client, template_db):
    session = template_db
    blockout_only = _template(session, "Blockout Twice", BLOCKOUT_ONLY)
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, blockout_only)
    preview = _preview(client, project_id, general.id)
    key = uuid.uuid4().hex
    first = _apply(client, project_id, preview, key=key)
    after_first = _snapshot(session, project_id)

    again = _apply(client, project_id, preview, key=key)
    assert again["replayed"] is True
    assert again["reconciliation"]["id"] == first["reconciliation"]["id"]
    assert _snapshot(session, project_id) == after_first

    stale = _apply(client, project_id, preview, expect=409)
    assert "preview again" in stale["detail"].lower()

    second = _preview(client, project_id, general.id)
    assert second["counts"]["add"] == 0 and second["counts"]["match"] == 7
    assert second["counts"]["merge"] == 0 and second["duplicates"] == []
    _apply(client, project_id, second)
    assert len(_milestones(session, project_id)) == 7


# --------------------------------------------------------------------------- safety


def test_preview_is_stale_after_concurrent_milestone_edit(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    preview = _preview(client, project_id, _template(session, "Concurrent", BLOCKOUT_ONLY).id)
    roughing = _by_name(session, project_id, "Roughing")
    roughing.name = "Roughing (rev B)"
    session.commit()
    body = _apply(client, project_id, preview, expect=409)
    assert "changed after your preview" in body["detail"]
    assert _get(session, Project, project_id).milestone_plan_version == 0


def test_legacy_apply_template_no_longer_replaces_milestones(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    _complete(session, _by_name(session, project_id, "Feasibility"), date(2026, 7, 1))
    before = _snapshot(session, project_id)
    response = client.post(
        f"/api/v1/projects/{project_id}/apply-template",
        json={"project_template_id": str(general.id)},
        headers=client.auth_headers,
    )
    assert response.status_code == 409
    assert _snapshot(session, project_id) == before
    read = client.get(f"/api/v1/projects/{project_id}", headers=client.auth_headers).json()
    assert read["can_change_template"] is True


def test_readonly_user_cannot_preview_or_apply(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, general)
    headers = login(client, "readonly@prosohm.com")
    response = client.post(
        f"/api/v1/projects/{project_id}/template-reconciliation/preview",
        json={"template_id": str(general.id)},
        headers=headers,
    )
    assert response.status_code == 403


def test_dependencies_follow_template_rules_without_cycles(client, template_db):
    session = template_db
    source = _template(session, "Dep Source", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Roughing", "stage": ProjectStage.preliminary, "deps": ["Blockout"]},
    ])
    target = _template(session, "Dep Target", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Design Review", "stage": ProjectStage.preliminary, "deps": ["Blockout"]},
        {"name": "Roughing", "stage": ProjectStage.preliminary, "deps": ["Design Review"]},
    ])
    project_id = _new_project(client, session, source)
    preview = _preview(client, project_id, target.id)
    new = next(n for n in preview["new_milestones"] if n["name"] == "Design Review")
    assert new["depends_on_names"] == ["Blockout"]
    assert new["sort_position"] == 2
    _apply(client, project_id, preview)

    review = _by_name(session, project_id, "Design Review")
    blockout = _by_name(session, project_id, "Blockout")
    roughing = _by_name(session, project_id, "Roughing")
    assert parse_id_list(review.depends_on_ids) == [str(blockout.id)]
    assert set(parse_id_list(roughing.depends_on_ids)) == {str(blockout.id), str(review.id)}
    assert [m.name for m in _milestones(session, project_id, active_only=True)] == ["Blockout", "Design Review", "Roughing"]


def test_template_hours_need_estimate_acknowledgement(client, template_db):
    session = template_db
    target = _template(session, "Hours Target", [
        {"name": "Blockout", "stage": ProjectStage.preliminary},
        {"name": "Release Pack", "hours": Decimal("12.5"), "offset": 400},
    ])
    project_id = _new_project(client, session, _template(session, "Hours Source", BLOCKOUT_ONLY))
    preview = _preview(client, project_id, target.id, apply_template_hours=True)
    assert preview["requires_estimate_acknowledgement"] is True
    assert Decimal(str(preview["planned_hours"]["after"])) - Decimal(str(preview["planned_hours"]["before"])) == Decimal("12.5")
    body = _apply(client, project_id, preview, apply_template_hours=True, expect=422)
    assert "acknowledge" in body["detail"].lower()
    _apply(client, project_id, preview, apply_template_hours=True, acknowledge_estimate_change=True)
    release = _by_name(session, project_id, "Release Pack")
    assert release.planned_hours == Decimal("12.50")
    project = _get(session, Project, project_id)
    assert release.due_date is None or release.due_date >= date.today()
    assert project.current_planned_hours is not None


def test_existing_due_dates_are_never_changed(client, template_db):
    session = template_db
    general = _template_by_name(session, "General Mold Design")
    project_id = _new_project(client, session, _template(session, "Dates Source", BLOCKOUT_ONLY))
    blockout = _by_name(session, project_id, "Blockout")
    blockout.due_date = date(2030, 1, 15)
    session.commit()
    _apply(client, project_id, _preview(client, project_id, general.id))
    assert _get(session, Milestone, blockout.id).due_date == date(2030, 1, 15)


def test_renamed_milestone_matches_through_template_version_lineage(client, template_db):
    session = template_db
    project_id = _new_project(client, session, _template(session, "Lineage Base", BLOCKOUT_ONLY))
    template = _get(session, Project, project_id).project_template
    row = template.milestones[0]
    response = client.patch(
        f"/api/v1/project-templates/{template.id}",
        json={"milestones": [{"id": str(row.id), "milestone_name": "Blockout Design", "sort_order": 1,
                              "project_stage": "preliminary", "is_required": True}]},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    new_version_id = response.json()["id"]
    assert new_version_id != str(template.id), "a template in use is versioned, not edited in place"
    blockout = _by_name(session, project_id, "Blockout")
    assert _get(session, Project, project_id).project_template_id == template.id, "projects are not auto-updated"

    preview = _preview(client, project_id, new_version_id)
    match = preview["matches"][0]
    assert match["milestone"]["id"] == str(blockout.id)
    assert match["classification"] == "confirmed"
    assert "another version" in match["reasons"][0]
