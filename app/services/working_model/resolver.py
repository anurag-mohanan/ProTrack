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


def resolve_working_models_for_projects(
    db: Session, projects: list[Project]
) -> dict[UUID, WorkingModel | None]:
    """Same precedence as ``resolve_working_model_for_project`` in two queries for any number of projects."""
    if not projects:
        return {}
    models = {model.id: model for model in db.scalars(select(WorkingModel))}
    customer_ids = {project.customer_id for project in projects if project.customer_id}
    customer_defaults = (
        dict(
            db.execute(
                select(Customer.id, Customer.default_working_model_id).where(
                    Customer.id.in_(customer_ids)
                )
            ).all()
        )
        if customer_ids
        else {}
    )
    defaults = sorted(
        (
            model
            for model in models.values()
            if model.code == WorkingModelCode.project_based.value
            and model.is_active
            and not model.is_archived
        ),
        key=lambda model: model.sort_order or 0,
    )
    fallback = defaults[0] if defaults else None
    result: dict[UUID, WorkingModel | None] = {}
    for project in projects:
        model = models.get(project.working_model_id) if project.working_model_id else None
        if model is None:
            customer_default = customer_defaults.get(project.customer_id)
            model = models.get(customer_default) if customer_default else None
        result[project.id] = model or fallback
    return result


def resolve_working_model_for_user(db: Session, user: User) -> WorkingModel | None:
    """Return the user's explicit default only — never invent a fallback.

    System admins and other non-billable accounts should keep
    ``default_working_model_id`` unset (None).
    """
    if user.default_working_model_id is None:
        return None
    return get_working_model_by_id(db, user.default_working_model_id)
