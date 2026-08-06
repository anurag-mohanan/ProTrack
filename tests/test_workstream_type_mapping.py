"""Project type → workstream default mapping for Command Center segregation."""

from __future__ import annotations

from app.db.workstream_seed import (
    ensure_project_type_workstream_defaults,
    ensure_workstream_catalog,
)
from app.models.models import ProjectType
from app.models.workstream import Workstream
from sqlalchemy import select


def test_project_type_default_workstream_seed(session):
    ensure_workstream_catalog(session)
    session.flush()

    cad = session.scalar(select(Workstream).where(Workstream.code == "CAD"))
    mold = session.scalar(select(Workstream).where(Workstream.code == "MOLD"))
    assert cad is not None and mold is not None

    # Ensure types exist without mapping
    for name in ("CAD Development", "Mold Design", "Unknown Specialty"):
        existing = session.scalar(select(ProjectType).where(ProjectType.name == name))
        if existing is None:
            session.add(ProjectType(name=name, is_active=True))
    session.flush()

    # Clear any prior defaults so seed re-applies
    for row in session.scalars(select(ProjectType)).all():
        row.default_workstream_id = None
    session.flush()

    updated = ensure_project_type_workstream_defaults(session)
    assert updated >= 2
    session.flush()

    cad_type = session.scalar(select(ProjectType).where(ProjectType.name == "CAD Development"))
    mold_type = session.scalar(select(ProjectType).where(ProjectType.name == "Mold Design"))
    assert cad_type is not None and mold_type is not None
    assert cad_type.default_workstream_id == cad.id
    assert mold_type.default_workstream_id == mold.id


def test_project_type_api_exposes_default_workstream(client, session):
    ensure_workstream_catalog(session)
    ensure_project_type_workstream_defaults(session)
    session.commit()

    response = client.get("/api/v1/lookups/project-types", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert isinstance(rows, list)
    if rows:
        assert "default_workstream_id" in rows[0]
