"""Management intelligence API: cockpit, customer intelligence and engineering efficiency.

Every figure comes from the existing Finance, delivery, capacity, skills and prediction services
through ``app.services.management``. Access is resolved server-side once per request: Reports
module plus project visibility and report scope; Finance figures only with Finance view access;
workforce figures only with Resource Planning or HR access.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, Response, status
from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.models.foundation import CompanySettings
from app.models.models import User
from app.schemas.management import (
    ActionCreate,
    ActionUpdate,
    ApprovalNote,
    CommentCreate,
    DecisionCreate,
    InitiativeCreate,
    InitiativeUpdate,
    MeasurementCreate,
    ObjectiveCreate,
    ObjectiveUpdate,
    ReviewCreate,
    ReviewUpdate,
    TargetChange,
)
from app.services.management import actions, exports, initiatives, kpis, objectives, reviews
from app.services.management.access import ManagementAccess, ManagementForbidden, resolve_access
from app.services.management.cockpit import build_cockpit, visible_definitions
from app.services.management.customers import build_customer_profile, build_customer_table
from app.services.management.efficiency import build_efficiency
from app.services.management.filters import CockpitFilters, build_filters, filter_options, resolve_period
from app.services.reporting.excel.management import generate_management_excel
from app.services.reporting.report_authorization import log_report_generation


def _access(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ManagementAccess:
    try:
        return resolve_access(db, current_user)
    except ManagementForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


router = APIRouter(prefix="/management", tags=["management"])


def _filters(
    db: Session = Depends(get_db),
    access: ManagementAccess = Depends(_access),
    fy_start_year: int | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    customer_id: UUID | None = Query(None),
    classification: str | None = Query(None),
    manager_id: UUID | None = Query(None),
    team_id: UUID | None = Query(None),
    business_unit: str | None = Query(None, max_length=120),
) -> CockpitFilters:
    try:
        period = resolve_period(db, fy_start_year=fy_start_year, start=start_date, end=end_date)
        return build_filters(db, access, period=period, customer_id=customer_id, classification=classification,
                             manager_id=manager_id, team_id=team_id, business_unit=business_unit)
    except ManagementForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ManagementForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _write(db: Session, fn, *args, **kwargs):
    """Run a change and commit it, or roll it back and map the error."""
    try:
        result = _run(fn, *args, **kwargs)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return result


@router.get("/filters")
def get_filters(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    return {**filter_options(db, access), "can": access.flags()}


@router.get("/definitions")
def get_definitions(access: ManagementAccess = Depends(_access)):
    return {"definitions": visible_definitions(access)}


@router.get("/cockpit")
def get_cockpit(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                filters: CockpitFilters = Depends(_filters)):
    return _run(build_cockpit, db, access, filters)


@router.get("/customers")
def list_customers(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                   filters: CockpitFilters = Depends(_filters)):
    return {"filters": filters.as_dict(), "can": access.flags(), **_run(build_customer_table, db, access, filters)}


@router.get("/customers/{profile_customer_id}")
def get_customer_profile(profile_customer_id: UUID, db: Session = Depends(get_db),
                         access: ManagementAccess = Depends(_access), filters: CockpitFilters = Depends(_filters)):
    return {"filters": filters.as_dict(), "can": access.flags(),
            **_run(build_customer_profile, db, access, filters, profile_customer_id)}


@router.get("/efficiency")
def get_efficiency(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                   filters: CockpitFilters = Depends(_filters), compare_by: str = Query("month", max_length=30)):
    return {"filters": filters.as_dict(), "can": access.flags(),
            **_run(build_efficiency, db, access, filters, compare_by=compare_by)}


# ----------------------------------------------------------------- strategic objectives


@router.get("/kpis")
def list_kpis(access: ManagementAccess = Depends(_access)):
    rows = [r for r in kpis.registry_list() if kpis.can_view(access, kpis.REGISTRY[r["key"]])[0] or access.manage]
    return {"kpis": rows}


@router.get("/objectives")
def list_objectives(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                    fy_start_year: int | None = Query(None), status_filter: str | None = Query(None, alias="status"),
                    category: str | None = Query(None)):
    return {"objectives": objectives.list_objectives(db, access, fy_start_year=fy_start_year, status=status_filter,
                                                     category=category),
            "can": access.flags()}


@router.post("/objectives", status_code=status.HTTP_201_CREATED)
def create_objective(body: ObjectiveCreate, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    obj = _write(db, objectives.create_objective, db, access, body)
    return objectives.serialize(db, access, obj, detail=True)


@router.get("/objectives/{objective_id}")
def get_objective(objective_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    return objectives.serialize(db, access, obj, detail=True)


@router.patch("/objectives/{objective_id}")
def update_objective(objective_id: UUID, body: ObjectiveUpdate, db: Session = Depends(get_db),
                     access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    _write(db, objectives.update_objective, db, access, obj, body)
    return objectives.serialize(db, access, obj, detail=True)


@router.post("/objectives/{objective_id}/target")
def change_objective_target(objective_id: UUID, body: TargetChange, db: Session = Depends(get_db),
                            access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    _write(db, objectives.change_target, db, access, obj, body)
    return objectives.serialize(db, access, obj, detail=True)


@router.post("/objectives/{objective_id}/approve-target")
def approve_objective_target(objective_id: UUID, body: ApprovalNote, db: Session = Depends(get_db),
                             access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    _write(db, objectives.approve_target, db, access, obj, body.note)
    return objectives.serialize(db, access, obj, detail=True)


@router.post("/objectives/{objective_id}/measurements", status_code=status.HTTP_201_CREATED)
def record_objective_measurement(objective_id: UUID, body: MeasurementCreate, db: Session = Depends(get_db),
                                 access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    _write(db, objectives.record_measurement, db, access, obj, body)
    return objectives.serialize(db, access, obj, detail=True)


@router.post("/objectives/{objective_id}/comments", status_code=status.HTTP_201_CREATED)
def comment_on_objective(objective_id: UUID, body: CommentCreate, db: Session = Depends(get_db),
                         access: ManagementAccess = Depends(_access)):
    obj = _run(objectives.get_objective, db, objective_id)
    _write(db, objectives.add_note, db, access, "objective", obj.id, kind=body.kind, text=body.text,
           editable=objectives.can_comment(access, obj.owner_id))
    return objectives.serialize(db, access, obj, detail=True)


# ----------------------------------------------------------------- initiatives


@router.get("/initiatives")
def list_initiatives(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                     objective_id: UUID | None = Query(None), status_filter: str | None = Query(None, alias="status")):
    return {"initiatives": initiatives.list_initiatives(db, access, objective_id=objective_id, status=status_filter),
            "can": access.flags()}


@router.post("/initiatives", status_code=status.HTTP_201_CREATED)
def create_initiative(body: InitiativeCreate, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    row = _write(db, initiatives.create_initiative, db, access, body)
    return initiatives.serialize(db, access, row, detail=True)


@router.get("/initiatives/{initiative_id}")
def get_initiative(initiative_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    return initiatives.serialize(db, access, _run(initiatives.get_initiative, db, initiative_id), detail=True)


@router.patch("/initiatives/{initiative_id}")
def update_initiative(initiative_id: UUID, body: InitiativeUpdate, db: Session = Depends(get_db),
                      access: ManagementAccess = Depends(_access)):
    row = _run(initiatives.get_initiative, db, initiative_id)
    _write(db, initiatives.update_initiative, db, access, row, body)
    return initiatives.serialize(db, access, row, detail=True)


@router.post("/initiatives/{initiative_id}/comments", status_code=status.HTTP_201_CREATED)
def comment_on_initiative(initiative_id: UUID, body: CommentCreate, db: Session = Depends(get_db),
                          access: ManagementAccess = Depends(_access)):
    row = _run(initiatives.get_initiative, db, initiative_id)
    _write(db, objectives.add_note, db, access, "initiative", row.id, kind=body.kind, text=body.text,
           editable=objectives.can_comment(access, row.owner_id))
    return initiatives.serialize(db, access, row, detail=True)


# ----------------------------------------------------------------- actions


@router.get("/actions")
def list_actions(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                 status_filter: str | None = Query(None, alias="status"), mine: bool = Query(False),
                 open_only: bool = Query(False), review_id: UUID | None = Query(None),
                 objective_id: UUID | None = Query(None)):
    return {"actions": actions.list_actions(db, access, status=status_filter, mine=mine, open_only=open_only,
                                            review_id=review_id, objective_id=objective_id),
            "summary": actions.outstanding_summary(db, access), "can": access.flags()}


@router.post("/actions", status_code=status.HTTP_201_CREATED)
def create_action(body: ActionCreate, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    row = _write(db, actions.create_action, db, access, body)
    return actions.serialize(db, row, detail=True, access=access)


@router.get("/actions/{action_id}")
def get_action(action_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    return actions.serialize(db, _run(actions.get_action, db, access, action_id), detail=True, access=access)


@router.patch("/actions/{action_id}")
def update_action(action_id: UUID, body: ActionUpdate, db: Session = Depends(get_db),
                  access: ManagementAccess = Depends(_access)):
    row = _run(actions.get_action, db, access, action_id)
    _write(db, actions.update_action, db, access, row, body)
    return actions.serialize(db, row, detail=True, access=access)


@router.post("/actions/{action_id}/comments", status_code=status.HTTP_201_CREATED)
def comment_on_action(action_id: UUID, body: CommentCreate, db: Session = Depends(get_db),
                      access: ManagementAccess = Depends(_access)):
    row = _run(actions.get_action, db, access, action_id)
    _write(db, objectives.add_note, db, access, "action", row.id, kind=body.kind, text=body.text,
           editable=actions.owner_or_manager(access, row.owner_id))
    return actions.serialize(db, row, detail=True, access=access)


# ----------------------------------------------------------------- management reviews


@router.get("/reviews")
def list_reviews(db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                 review_type: str | None = Query(None), fy_start_year: int | None = Query(None)):
    return {"reviews": _run(reviews.list_reviews, db, access, review_type=review_type, fy_start_year=fy_start_year),
            "can": access.flags()}


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
def create_review(body: ReviewCreate, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    row = _write(db, reviews.create_review, db, access, body)
    return reviews.serialize(db, access, row, detail=True)


@router.get("/reviews/{review_id}")
def get_review(review_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    return reviews.serialize(db, access, _run(reviews.get_review, db, access, review_id), detail=True)


@router.patch("/reviews/{review_id}")
def update_review(review_id: UUID, body: ReviewUpdate, db: Session = Depends(get_db),
                  access: ManagementAccess = Depends(_access)):
    row = _run(reviews.get_review, db, access, review_id)
    _write(db, reviews.update_review, db, access, row, body)
    return reviews.serialize(db, access, row, detail=True)


@router.post("/reviews/{review_id}/regenerate")
def regenerate_review(review_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    row = _run(reviews.get_review, db, access, review_id)
    _write(db, reviews.regenerate, db, access, row)
    return reviews.serialize(db, access, row, detail=True)


@router.post("/reviews/{review_id}/finalise")
def finalise_review(review_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access)):
    row = _run(reviews.get_review, db, access, review_id)
    _write(db, reviews.finalise, db, access, row)
    return reviews.serialize(db, access, row, detail=True)


@router.post("/reviews/{review_id}/decisions", status_code=status.HTTP_201_CREATED)
def record_review_decision(review_id: UUID, body: DecisionCreate, db: Session = Depends(get_db),
                           access: ManagementAccess = Depends(_access)):
    row = _run(reviews.get_review, db, access, review_id)
    _write(db, reviews.record_decision, db, access, row, body)
    return reviews.serialize(db, access, row, detail=True)


@router.post("/reviews/{review_id}/comments", status_code=status.HTTP_201_CREATED)
def comment_on_review(review_id: UUID, body: CommentCreate, db: Session = Depends(get_db),
                      access: ManagementAccess = Depends(_access)):
    row = _run(reviews.get_review, db, access, review_id)
    if body.kind == "decision":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Record review decisions through the decisions endpoint.")
    _write(db, objectives.add_note, db, access, "review", row.id, kind="comment", text=body.text, editable=True)
    return reviews.serialize(db, access, row, detail=True)


@router.get("/reviews/{review_id}/compare")
def compare_review(review_id: UUID, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                   other: UUID | None = Query(None, alias="with")):
    row = _run(reviews.get_review, db, access, review_id)
    return _run(reviews.compare, db, access, row, other)


# ----------------------------------------------------------------- exports


@router.get("/exports/{report}.xlsx")
def export_management_report(report: str, db: Session = Depends(get_db), access: ManagementAccess = Depends(_access),
                             filters: CockpitFilters = Depends(_filters),
                             compare_by: str = Query("month", max_length=30), review_id: UUID | None = Query(None)):
    sheets = _run(exports.build_export, db, access, report, filters, compare_by=compare_by, review_id=review_id)
    settings = db.scalar(select(CompanySettings).limit(1))
    company_name = settings.company_name if settings and settings.company_name else "ProTrack"
    content = generate_management_excel(sheets, company_name=company_name)
    period = filters.period
    span = f"review_{review_id}" if report == "review" else f"{period.start:%Y%m%d}-{period.end:%Y%m%d}"
    filename = f"Management_{report.replace('-', '_')}_{span}.xlsx"
    log_report_generation(db, user=access.user, report_type=f"management-{report}",
                          filters={**filters.as_dict(), "compare_by": compare_by if report == "efficiency" else None,
                                   "review_id": str(review_id) if review_id else None},
                          team_id=filters.team_id, filename=filename, module="management")
    return Response(content=content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
