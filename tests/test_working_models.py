"""Tests for working models master data, migration, and KPI strategies."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.phase15_working_model_schema_sync import ensure_phase15_working_model_foundation
from app.models.enums import WorkingModelCode
from app.models.models import Customer, Project, WorkingModel
from app.services.project_calculation_service import calculate_hours
from app.services.working_model.engine import WorkingModelEngine
from app.services.working_model.registry import build_default_registry


@pytest.fixture()
def working_models(session, test_engine):
    ensure_phase15_working_model_foundation(test_engine)
    session.expire_all()
    return {
        row.code: row
        for row in session.scalars(select(WorkingModel).order_by(WorkingModel.sort_order)).all()
    }


def test_seed_working_models(working_models):
    assert set(working_models) == {"project_based", "time_materials", "retainer", "overheads"}
    assert working_models["project_based"].name == "Project Based (Fixed Fee)"
    assert working_models["project_based"].strategy_key == WorkingModelCode.project_based
    assert working_models["overheads"].name == "Overheads"
    assert working_models["overheads"].strategy_key == WorkingModelCode.overheads


def test_existing_projects_backfilled_to_project_based(session, test_engine, working_models):
    ensure_phase15_working_model_foundation(test_engine)
    project = session.scalar(select(Project).limit(1))
    assert project is not None
    assert project.working_model_id == working_models["project_based"].id


def test_customer_default_inherited_on_project_create(session, working_models):
    customer = session.scalar(select(Customer).limit(1))
    assert customer is not None
    customer.default_working_model_id = working_models["retainer"].id
    session.add(customer)
    session.commit()

    from app.crud.project import _prepare_project_create
    from app.schemas.project import ProjectCreate

    prepared = _prepare_project_create(
        session,
        ProjectCreate(
            tool_number=f"WM-{uuid4().hex[:6]}",
            part_description="Working model inheritance test",
            customer_id=customer.id,
        ),
    )
    assert prepared.working_model_id == working_models["retainer"].id


def test_project_based_strategy_kpis(session, working_models):
    project = session.scalar(select(Project).limit(1))
    assert project is not None
    project.working_model_id = working_models["project_based"].id
    session.add(project)
    session.commit()
    session.refresh(project)

    result = WorkingModelEngine(session).calculate_kpis(project)
    assert result is not None
    assert result.show_quoted_variance is True
    assert result.variance is not None
    assert result.quoted_hours is not None


def test_time_materials_strategy_hides_quote_variance(session, working_models):
    project = session.scalar(select(Project).limit(1))
    assert project is not None
    project.working_model_id = working_models["time_materials"].id
    project.quoted_hours = Decimal("100")
    session.add(project)
    session.commit()
    session.refresh(project)

    engine = WorkingModelEngine(session)
    hours = calculate_hours(session, project)
    result = engine.calculate_kpis(project, hours=hours)
    assert result is not None
    assert result.show_quoted_variance is False
    assert result.variance is None
    assert result.model_metrics.get("billable_hours") is not None
    assert engine.should_flag_hours_over_quote(project, hours) is False


def test_retainer_strategy_uses_capacity_metrics(session, working_models):
    project = session.scalar(select(Project).limit(1))
    assert project is not None
    project.working_model_id = working_models["retainer"].id
    project.quoted_hours = Decimal("40")
    session.add(project)
    session.commit()
    session.refresh(project)

    result = WorkingModelEngine(session).calculate_kpis(project)
    assert result is not None
    assert result.show_over_budget_indicators is False
    assert result.model_metrics.get("monthly_capacity_hours") == Decimal("40")


def test_registry_lists_all_strategies():
    registry = build_default_registry()
    keys = registry.available_strategy_keys()
    assert WorkingModelCode.project_based in keys
    assert WorkingModelCode.time_materials in keys
    assert WorkingModelCode.retainer in keys
    assert WorkingModelCode.overheads in keys


def test_overheads_strategy_hides_quote_variance(session, working_models):
    project = session.scalar(select(Project).limit(1))
    assert project is not None
    project.working_model_id = working_models["overheads"].id
    session.add(project)
    session.commit()
    session.refresh(project)

    engine = WorkingModelEngine(session)
    hours = calculate_hours(session, project)
    result = engine.calculate_kpis(project, hours=hours)
    assert result is not None
    assert result.strategy_key == WorkingModelCode.overheads
    assert result.show_quoted_variance is False
    assert result.show_over_budget_indicators is False
    assert result.model_metrics.get("resource_class") == "management_overhead"
    assert engine.should_flag_hours_over_quote(project, hours) is False
