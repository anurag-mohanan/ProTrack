from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — register all models with Base.metadata
import app.models.finance  # noqa: F401 — register finance models
from app.api.v1.api import api_router
from app.core.config import APP_VERSION, CORS_ORIGINS, ENABLE_DEMO_SEED, INTERNAL_RELEASE, RELEASE_CANDIDATE, UPLOAD_DIR
from app.core.openapi import fix_ref_siblings
from app.db.base import Base
from app.db.project_template_seed import (
    ensure_project_types_and_templates,
    validate_project_template_health,
)
from app.db.phase7_schema_sync import ensure_phase7_foundation
from app.db.phase8_schema_sync import ensure_phase8_foundation
from app.db.phase9_schema_sync import ensure_phase9_foundation
from app.db.phase10_milestone_schema_sync import ensure_phase10_milestone_foundation
from app.db.phase11_email_schema_sync import ensure_email_foundation
from app.db.phase12_email_communication_schema_sync import ensure_email_communication_foundation
from app.db.phase13_multi_team_schema_sync import ensure_phase13_multi_team_foundation
from app.db.phase14_kpi_schema_sync import ensure_phase14_kpi_foundation
from app.db.phase15_working_model_schema_sync import ensure_phase15_working_model_foundation
from app.db.phase16_timesheet_contribution_schema_sync import ensure_phase16_timesheet_contribution_foundation
from app.db.phase17_ebmp_finance_schema_sync import ensure_phase17_ebmp_finance_foundation
from app.db.phase18_finance_annual_plan_schema_sync import (
    ensure_phase18_finance_annual_plan_foundation,
)
from app.db.phase19_timesheet_report_inclusion_schema_sync import (
    ensure_phase19_timesheet_report_inclusion_foundation,
)
from app.db.phase20_project_complexity_schema_sync import ensure_project_complexity
from app.db.phase21_project_workorder_schema_sync import ensure_project_workorder_metadata
from app.db.phase22_finance_rebuild_schema_sync import ensure_phase22_finance_rebuild_foundation
from app.db.phase23_finance_team_scope_schema_sync import (
    ensure_phase23_finance_team_scope_foundation,
)
from app.db.phase24_user_requires_salary_schema_sync import (
    ensure_phase24_user_requires_salary_foundation,
)
from app.db.phase25_expense_purchase_date_schema_sync import (
    ensure_phase25_expense_purchase_date_foundation,
)
from app.db.phase26_customer_currency_schema_sync import (
    ensure_phase26_customer_currency_foundation,
)
from app.db.phase27_fx_rate_backfill import ensure_phase27_fx_rate_backfill
from app.db.phase28_team_member_billable_schema_sync import (
    ensure_phase28_team_member_billable_foundation,
)
from app.db.schema_sync import (
    ensure_admin_schema,
    ensure_design_roles,
    ensure_production_roles,
    ensure_performance_indexes,
    ensure_design_team,
    ensure_project_lifecycle_schema,
    ensure_project_stage_and_execution_status,
    ensure_placeholder_project_schema,
    ensure_project_timestamps,
    ensure_project_template_schema,
    ensure_project_actual_hours,
    ensure_project_health,
    ensure_non_productive_codes,
    ensure_standard_task_types,
    ensure_timesheet_entry_work_category,
    ensure_timesheet_entry_hours_constraint,
    ensure_timesheet_entry_leave_count,
    ensure_timesheet_entry_timestamps,
    ensure_timesheet_entry_soft_delete,
    ensure_timesheet_approval_comments,
    ensure_team_schema,
    ensure_user_team_schema,
    ensure_user_lifecycle_schema,
    ensure_user_auth_schema,
    ensure_user_access_schema,
)
from app.db.session import engine, sessionmaker


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger("protrack.startup")
    Base.metadata.create_all(bind=engine)

    startup_steps = [
        ("project_actual_hours", ensure_project_actual_hours),
        ("project_health", ensure_project_health),
        ("timesheet_approval_comments", ensure_timesheet_approval_comments),
        ("design_roles", ensure_design_roles),
        ("production_roles", ensure_production_roles),
        ("admin_schema", ensure_admin_schema),
        ("project_template_schema", ensure_project_template_schema),
        ("project_lifecycle_schema", ensure_project_lifecycle_schema),
        ("project_stage_and_execution_status", ensure_project_stage_and_execution_status),
        ("placeholder_project_schema", ensure_placeholder_project_schema),
        ("project_timestamps", ensure_project_timestamps),
        ("team_schema", ensure_team_schema),
        ("user_team_schema", ensure_user_team_schema),
        ("user_lifecycle_schema", ensure_user_lifecycle_schema),
        ("user_auth_schema", ensure_user_auth_schema),
        ("user_access_schema", ensure_user_access_schema),
        ("phase15_working_model", ensure_phase15_working_model_foundation),
        ("timesheet_entry_work_category", ensure_timesheet_entry_work_category),
        ("timesheet_entry_hours_constraint", ensure_timesheet_entry_hours_constraint),
        ("timesheet_entry_timestamps", ensure_timesheet_entry_timestamps),
        ("timesheet_entry_soft_delete", ensure_timesheet_entry_soft_delete),
        ("phase16_timesheet_contribution", ensure_phase16_timesheet_contribution_foundation),
        ("non_productive_codes", ensure_non_productive_codes),
        ("timesheet_entry_leave_count", ensure_timesheet_entry_leave_count),
        ("phase14_kpi", ensure_phase14_kpi_foundation),
        ("standard_task_types", ensure_standard_task_types),
        ("phase7", ensure_phase7_foundation),
        ("phase8", ensure_phase8_foundation),
        ("phase9", ensure_phase9_foundation),
        ("phase10_milestone", ensure_phase10_milestone_foundation),
        ("email_foundation", ensure_email_foundation),
        ("email_communication", ensure_email_communication_foundation),
        ("phase13_multi_team", ensure_phase13_multi_team_foundation),
        ("phase17_ebmp_finance", ensure_phase17_ebmp_finance_foundation),
        ("phase18_finance_annual_plan", ensure_phase18_finance_annual_plan_foundation),
        ("phase19_timesheet_report_inclusion", ensure_phase19_timesheet_report_inclusion_foundation),
        ("project_complexity", ensure_project_complexity),
        ("project_workorder_metadata", ensure_project_workorder_metadata),
        ("phase22_finance_rebuild", ensure_phase22_finance_rebuild_foundation),
        ("phase23_finance_team_scope", ensure_phase23_finance_team_scope_foundation),
        ("phase24_user_requires_salary", ensure_phase24_user_requires_salary_foundation),
        ("phase25_expense_purchase_date", ensure_phase25_expense_purchase_date_foundation),
        ("phase26_customer_currency", ensure_phase26_customer_currency_foundation),
        ("phase27_fx_rate_backfill", ensure_phase27_fx_rate_backfill),
        ("phase28_team_member_billable", ensure_phase28_team_member_billable_foundation),
        ("performance_indexes", ensure_performance_indexes),
    ]

    failures: list[str] = []
    for name, step in startup_steps:
        try:
            step(engine)
        except Exception:
            failures.append(name)
            logger.exception("Startup schema step failed: %s", name)

    if ENABLE_DEMO_SEED:
        try:
            ensure_design_team(engine)
        except Exception:
            failures.append("design_team_seed")
            logger.exception("Demo design team seed failed")

    seed_session = sessionmaker(bind=engine)()
    try:
        ensure_project_types_and_templates(seed_session)
        validate_project_template_health(seed_session)
    except Exception:
        failures.append("project_template_seed")
        logger.exception("Project template seed/validation failed")
    finally:
        seed_session.close()

    if failures:
        logger.error(
            "ProTrack API started with schema step failures: %s. "
            "Login/API may still work; fix and restart before release.",
            ", ".join(failures),
        )
    else:
        logger.info("ProTrack API startup schema sync completed successfully")

    yield


app = FastAPI(
    title="ProTrack API",
    description="Engineering management platform API for Prosohm Projects Pvt. Ltd.",
    version=f"{APP_VERSION}-{RELEASE_CANDIDATE.lower()}",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": False,
    },
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description or "",
        routes=app.routes,
    )
    app.openapi_schema = fix_ref_siblings(schema)
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "ProTrack",
        "version": APP_VERSION,
        "release": RELEASE_CANDIDATE,
        "internal_release": INTERNAL_RELEASE,
    }
