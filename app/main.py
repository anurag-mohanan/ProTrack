from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — register all models with Base.metadata
from app.api.v1.api import api_router
from app.core.config import APP_VERSION, CORS_ORIGINS, ENABLE_DEMO_SEED, INTERNAL_RELEASE, RELEASE_CANDIDATE, UPLOAD_DIR
from app.core.openapi import fix_ref_siblings
from app.db.base import Base
from app.db.project_template_seed import ensure_project_types_and_templates
from app.db.phase7_schema_sync import ensure_phase7_foundation
from app.db.phase8_schema_sync import ensure_phase8_foundation
from app.db.phase9_schema_sync import ensure_phase9_foundation
from app.db.phase10_milestone_schema_sync import ensure_phase10_milestone_foundation
from app.db.phase11_email_schema_sync import ensure_email_foundation
from app.db.phase12_email_communication_schema_sync import ensure_email_communication_foundation
from app.db.phase13_multi_team_schema_sync import ensure_phase13_multi_team_foundation
from app.db.phase14_kpi_schema_sync import ensure_phase14_kpi_foundation
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
    Base.metadata.create_all(bind=engine)
    ensure_project_actual_hours(engine)
    ensure_project_health(engine)
    ensure_timesheet_approval_comments(engine)
    ensure_design_roles(engine)
    ensure_production_roles(engine)
    ensure_admin_schema(engine)
    ensure_project_template_schema(engine)
    ensure_project_lifecycle_schema(engine)
    ensure_project_stage_and_execution_status(engine)
    ensure_placeholder_project_schema(engine)
    ensure_project_timestamps(engine)
    ensure_team_schema(engine)
    ensure_user_team_schema(engine)
    ensure_user_lifecycle_schema(engine)
    ensure_user_auth_schema(engine)
    ensure_user_access_schema(engine)
    ensure_timesheet_entry_work_category(engine)
    ensure_timesheet_entry_hours_constraint(engine)
    ensure_timesheet_entry_timestamps(engine)
    ensure_timesheet_entry_soft_delete(engine)
    ensure_non_productive_codes(engine)
    ensure_timesheet_entry_leave_count(engine)
    ensure_phase14_kpi_foundation(engine)
    ensure_standard_task_types(engine)
    ensure_phase7_foundation(engine)
    ensure_phase8_foundation(engine)
    ensure_phase9_foundation(engine)
    ensure_phase10_milestone_foundation(engine)
    ensure_email_foundation(engine)
    ensure_email_communication_foundation(engine)
    ensure_phase13_multi_team_foundation(engine)
    ensure_performance_indexes(engine)
    if ENABLE_DEMO_SEED:
        ensure_design_team(engine)
    seed_session = sessionmaker(bind=engine)()
    try:
        ensure_project_types_and_templates(seed_session)
    finally:
        seed_session.close()
    yield


app = FastAPI(
    title="ProTrack API",
    description="Engineering management platform API for Prosohm Projects Pvt. Ltd.",
    version=f"{APP_VERSION}-rc4",
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
