"""Milestone-driven project stage and completion sync."""

from __future__ import annotations

from decimal import Decimal
import uuid

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectStage
from app.models.models import Customer, Milestone, Project, ProjectStageHistory, ProjectType, Team, User
from app.services import project_stage_sync_service as sync
from app.crud.milestone import milestone as milestone_crud
from app.schemas.project import MilestoneUpdate


def _admin(session):
    return session.query(User).filter(User.email == "admin@prosohm.com").first()


def _make_project_with_milestones(session, *, names_stages: list[tuple[str, ProjectStage | None]]):
    actor = _admin(session)
    assert actor
    customer = session.query(Customer).first()
    ptype = session.query(ProjectType).first()
    team = session.query(Team).first()
    assert customer and ptype
    project = Project(
        id=uuid.uuid4(),
        code=f"T{uuid.uuid4().hex[:6].upper()}",
        tool_number=f"3176-{uuid.uuid4().hex[:4]}",
        part_description="Stage sync test part",
        customer_id=customer.id,
        project_type_id=ptype.id if ptype else None,
        team_id=team.id if team else None,
        project_stage=ProjectStage.feasibility,
        execution_status=ExecutionStatus.currently_being_worked_on,
        quoted_hours=Decimal("40"),
    )
    session.add(project)
    session.flush()
    for order, (name, stage) in enumerate(names_stages):
        session.add(
            Milestone(
                project_id=project.id,
                name=name,
                status=MilestoneStatus.not_started,
                sort_order=order,
                is_required=True,
                project_stage=stage,
            )
        )
    session.commit()
    session.refresh(project)
    return project, actor


def test_single_milestone_does_not_complete_project(session):
    project, actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("Blockout", ProjectStage.preliminary),
            ("BOM Release", None),
        ],
    )
    feasibility = (
        session.query(Milestone)
        .filter(Milestone.project_id == project.id, Milestone.name == "Feasibility")
        .one()
    )
    milestone_crud.update(
        session,
        db_obj=feasibility,
        obj_in=MilestoneUpdate(status=MilestoneStatus.completed, progress_percent=100),
        actor=actor,
    )
    session.refresh(project)
    assert project.project_stage == ProjectStage.feasibility
    assert project.execution_status != ExecutionStatus.completed


def test_blockout_advances_to_preliminary(session):
    project, actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("Blockout", ProjectStage.preliminary),
            ("Intermediate Review", ProjectStage.intermediate),
        ],
    )
    for name in ("Feasibility", "Blockout"):
        row = (
            session.query(Milestone)
            .filter(Milestone.project_id == project.id, Milestone.name == name)
            .one()
        )
        milestone_crud.update(
            session,
            db_obj=row,
            obj_in=MilestoneUpdate(status=MilestoneStatus.completed, progress_percent=100),
            actor=actor,
        )
    session.refresh(project)
    assert project.project_stage == ProjectStage.preliminary
    assert project.execution_status != ExecutionStatus.completed


def test_all_required_complete_marks_project_completed(session):
    project, actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("Blockout", ProjectStage.preliminary),
            ("BOM Release", None),
        ],
    )
    for row in session.query(Milestone).filter(Milestone.project_id == project.id).all():
        milestone_crud.update(
            session,
            db_obj=row,
            obj_in=MilestoneUpdate(status=MilestoneStatus.completed, progress_percent=100),
            actor=actor,
        )
    session.refresh(project)
    assert project.project_stage == ProjectStage.completed
    assert project.execution_status == ExecutionStatus.completed
    assert project.completed_at is not None
    history = (
        session.query(ProjectStageHistory)
        .filter(ProjectStageHistory.project_id == project.id)
        .all()
    )
    assert history
    assert any(row.new_stage == ProjectStage.completed.value for row in history)


def test_out_of_order_file_release_does_not_jump_stage(session):
    project, actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("Blockout", ProjectStage.preliminary),
            ("File Release", None),
        ],
    )
    file_release = (
        session.query(Milestone)
        .filter(Milestone.project_id == project.id, Milestone.name == "File Release")
        .one()
    )
    milestone_crud.update(
        session,
        db_obj=file_release,
        obj_in=MilestoneUpdate(status=MilestoneStatus.completed, progress_percent=100),
        actor=actor,
    )
    session.refresh(project)
    assert project.project_stage == ProjectStage.feasibility
    assert project.execution_status != ExecutionStatus.completed


def test_reopen_required_milestone_leaves_completed(session):
    project, actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("BOM Release", None),
        ],
    )
    for row in session.query(Milestone).filter(Milestone.project_id == project.id).all():
        milestone_crud.update(
            session,
            db_obj=row,
            obj_in=MilestoneUpdate(status=MilestoneStatus.completed, progress_percent=100),
            actor=actor,
        )
    session.refresh(project)
    assert project.execution_status == ExecutionStatus.completed
    original_completed_at = project.completed_at

    bom = (
        session.query(Milestone)
        .filter(Milestone.project_id == project.id, Milestone.name == "BOM Release")
        .one()
    )
    milestone_crud.update(
        session,
        db_obj=bom,
        obj_in=MilestoneUpdate(status=MilestoneStatus.in_progress, progress_percent=50),
        actor=actor,
    )
    session.refresh(project)
    assert project.execution_status == ExecutionStatus.currently_being_worked_on
    assert project.project_stage != ProjectStage.completed
    assert project.completed_at == original_completed_at


def test_calculate_stage_pure_function(session):
    project, _actor = _make_project_with_milestones(
        session,
        names_stages=[
            ("Feasibility", ProjectStage.feasibility),
            ("Blockout", ProjectStage.preliminary),
        ],
    )
    assert sync.calculate_project_stage(session, project.id) == ProjectStage.feasibility
    assert sync.evaluate_project_completion(session, project.id) is False
