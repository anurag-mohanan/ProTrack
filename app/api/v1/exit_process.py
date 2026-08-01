"""Exit process API — PP-HRD-FO-30 Employee Exit Interview."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.exceptions import ProTrackValidationError
from app.models.models import User
from app.schemas.exit_process import (
    ExitInterviewCreate,
    ExitInterviewQuestion,
    ExitInterviewRead,
    ExitInterviewUpdate,
)
from app.services import exit_process_service as exit_svc
from app.services.hr_form_publish import assert_can_delete, publish_document

router = APIRouter(prefix="/hr/exit-process", tags=["exit-process"])


def _require_access(db: Session, user: User) -> None:
    if not exit_svc.can_manage_exit_process(db, user):
        raise HTTPException(status_code=403, detail="Exit process access required")


def _questions() -> list[ExitInterviewQuestion]:
    return [ExitInterviewQuestion(**q) for q in exit_svc.EXIT_INTERVIEW_QUESTIONS]


def _read(row) -> ExitInterviewRead:
    return ExitInterviewRead(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        form_code=row.form_code or exit_svc.FORM_CODE,
        form_title=exit_svc.FORM_TITLE,
        employee_user_id=row.employee_user_id,
        employee_name=row.employee_name,
        employee_code=row.employee_code,
        designation=row.designation,
        department_name=row.department_name,
        org_department_id=row.org_department_id,
        team_id=row.team_id,
        team_name=row.team_name,
        role_id=row.role_id,
        role_name=row.role_name,
        reporting_manager_id=row.reporting_manager_id,
        reporting_manager_name=row.reporting_manager_name,
        last_working_date=row.last_working_date,
        resignation_date=row.resignation_date,
        interview_date=row.interview_date,
        interviewer_user_id=row.interviewer_user_id,
        interviewer_name=row.interviewer_name,
        status=row.status,
        status_label=exit_svc.STATUS_LABELS.get(row.status, row.status),
        answers=exit_svc.parse_answers(row.answers_json),
        notes=row.notes,
        attitude_was_good=getattr(row, "attitude_was_good", None),
        skillset_rating=getattr(row, "skillset_rating", None),
        eligible_for_rehire=getattr(row, "eligible_for_rehire", None),
        created_by_id=row.created_by_id,
        completed_at=row.completed_at,
        is_published=bool(getattr(row, "is_published", False)),
        published_at=getattr(row, "published_at", None),
        published_by_id=getattr(row, "published_by_id", None),
        questions=_questions(),
    )


@router.get("/form", response_model=list[ExitInterviewQuestion])
def get_exit_interview_form(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    return _questions()


@router.get("", response_model=list[ExitInterviewRead])
def list_exit_interviews(
    status_filter: str | None = Query(default="all", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    rows = exit_svc.list_exit_interviews(db, status=status_filter)
    return [_read(row) for row in rows]


@router.post("", response_model=ExitInterviewRead, status_code=status.HTTP_201_CREATED)
def create_exit_interview(
    payload: ExitInterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    row = exit_svc.create_exit_interview(
        db,
        current_user=current_user,
        employee_name=payload.employee_name,
        employee_user_id=payload.employee_user_id,
        employee_code=payload.employee_code,
        designation=payload.designation,
        department_name=payload.department_name,
        org_department_id=payload.org_department_id,
        team_id=payload.team_id,
        role_id=payload.role_id,
        reporting_manager_id=payload.reporting_manager_id,
        reporting_manager_name=payload.reporting_manager_name,
        last_working_date=payload.last_working_date,
        resignation_date=payload.resignation_date,
        interview_date=payload.interview_date,
        interviewer_user_id=payload.interviewer_user_id,
        interviewer_name=payload.interviewer_name,
        notes=payload.notes,
        answers=payload.answers,
    )
    return _read(row)


@router.get("/{interview_id}", response_model=ExitInterviewRead)
def get_exit_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    row = exit_svc.get_exit_interview(db, interview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Exit interview not found")
    return _read(row)


@router.patch("/{interview_id}", response_model=ExitInterviewRead)
def update_exit_interview(
    interview_id: UUID,
    payload: ExitInterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    row = exit_svc.get_exit_interview(db, interview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Exit interview not found")
    data = payload.model_dump(exclude_unset=True)
    try:
        row = exit_svc.update_exit_interview(
            db, row, data=data, actor=current_user
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    return _read(row)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exit_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    row = exit_svc.get_exit_interview(db, interview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Exit interview not found")
    try:
        assert_can_delete(row, document_label="exit interview")
        exit_svc.delete_exit_interview(db, row)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return None


@router.post("/{interview_id}/publish", response_model=ExitInterviewRead)
def publish_exit_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(db, current_user)
    row = exit_svc.get_exit_interview(db, interview_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Exit interview not found")
    try:
        publish_document(row, user=current_user)
        db.commit()
        db.refresh(row)
        return _read(row)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
