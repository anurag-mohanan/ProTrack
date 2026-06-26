from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

import app.models  # noqa: F401 — register all models with Base.metadata
from app.api.v1.api import api_router
from app.core.openapi import fix_ref_siblings
from app.db.base import Base
from app.db.schema_sync import (
    ensure_admin_schema,
    ensure_design_roles,
    ensure_design_team,
    ensure_project_actual_hours,
    ensure_project_health,
    ensure_timesheet_approval_comments,
)
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_project_actual_hours(engine)
    ensure_project_health(engine)
    ensure_timesheet_approval_comments(engine)
    ensure_design_roles(engine)
    ensure_admin_schema(engine)
    ensure_design_team(engine)
    yield


app = FastAPI(
    title="ProTrack API",
    description="Project tracking and resource planning API for Prosohm",
    version="0.1.0",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
