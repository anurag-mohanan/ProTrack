"""Resolve working model for projects, customers, and users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import WorkingModelCode
from app.models.models import Customer, Project, User, WorkingModel


def get_working_model_by_id(db: Session, model_id: UUID | None) -> WorkingModel | None:
    if model_id is None:
        return None
    return db.get(WorkingModel, model_id)


def get_default_working_model(db: Session) -> WorkingModel | None:
    return db.scalar(
        select(WorkingModel)
        .where(
            WorkingModel.code == WorkingModelCode.project_based.value,
            WorkingModel.is_active.is_(True),
            WorkingModel.is_archived.is_(False),
        )
        .order_by(WorkingModel.sort_order)
    )


def resolve_working_model_for_project(
    db: Session,
    *,
    project: Project | None = None,
    customer: Customer | None = None,
    working_model_id: UUID | None = None,
) -> WorkingModel | None:
    if working_model_id is not None:
        model = get_working_model_by_id(db, working_model_id)
        if model is not None:
            return model

    if project is not None and project.working_model_id is not None:
        model = get_working_model_by_id(db, project.working_model_id)
        if model is not None:
            return model

    if customer is None and project is not None:
        customer = project.customer

    if customer is not None and customer.default_working_model_id is not None:
        model = get_working_model_by_id(db, customer.default_working_model_id)
        if model is not None:
            return model

    return get_default_working_model(db)


def resolve_working_model_for_user(db: Session, user: User) -> WorkingModel | None:
    """Return the user's explicit default only — never invent a fallback.

    System admins and other non-billable accounts should keep
    ``default_working_model_id`` unset (None).
    """
    if user.default_working_model_id is None:
        return None
    return get_working_model_by_id(db, user.default_working_model_id)
