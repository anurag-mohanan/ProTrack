from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.core.password_policy import PASSWORD_REQUIREMENTS_MESSAGE
from app.schemas.operations import DiagnosticsReport, HealthSnapshotPoint, LogLine, OperationsCenterSnapshot
from app.schemas.system import SystemHealthRead
from app.services.backup_service import create_database_backup, list_database_backups, restore_database_backup
from app.services.health_history_store import get_history
from app.services.operations_center_service import (
    get_operations_snapshot,
    optimize_database,
    run_diagnostics,
    run_integrity_check,
    run_maintenance_action,
    tail_logs,
)
from app.services.system_health_service import get_system_health

router = APIRouter(prefix="/system", tags=["system"])
admin = Depends(require_roles("Admin"))
ops_read = Depends(require_roles("Admin", "Engineering Manager"))


@router.get("/operations", response_model=OperationsCenterSnapshot)
def read_operations_center(
    db: Session = Depends(get_db),
    _user=ops_read,
):
    return get_operations_snapshot(db)


@router.get("/operations/history", response_model=list[HealthSnapshotPoint])
def read_operations_history(
    period: str = "24h",
    _user=ops_read,
):
    return get_history(period)


@router.post("/operations/diagnostics", response_model=DiagnosticsReport)
def run_operations_diagnostics(
    db: Session = Depends(get_db),
    _admin=admin,
):
    return run_diagnostics(db)


@router.post("/operations/integrity-check")
def run_db_integrity_check(
    db: Session = Depends(get_db),
    _admin=admin,
):
    result = run_integrity_check(db)
    return {"status": "ok" if result.lower() == "ok" else "warning", "result": result}


@router.post("/operations/optimize")
def run_db_optimize(
    db: Session = Depends(get_db),
    _admin=admin,
):
    message = optimize_database(db)
    return {"status": "ok", "message": message}


@router.post("/operations/maintenance")
def run_maintenance(
    payload: dict[str, str],
    db: Session = Depends(get_db),
    _admin=admin,
):
    action = payload.get("action", "")
    try:
        return run_maintenance_action(action, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/operations/logs", response_model=list[LogLine])
def read_operations_logs(
    category: str = "application",
    limit: int = 100,
    _user=ops_read,
):
    return tail_logs(category, limit=min(limit, 500))


@router.get("/health", response_model=SystemHealthRead)
def read_system_health(
    db: Session = Depends(get_db),
    _admin=admin,
):
    return get_system_health(db)


@router.get("/security-policy")
def read_security_policy(_admin=admin):
    return {
        "password_requirements": PASSWORD_REQUIREMENTS_MESSAGE,
        "session_timeout_minutes": 480,
        "internal_release_mode": True,
    }


@router.get("/backups")
def list_backups(_admin=admin):
    return list_database_backups()


@router.post("/backups")
def create_backup(_admin=admin):
    try:
        return create_database_backup()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/backups/restore")
def restore_backup(payload: dict[str, str], _admin=admin):
    filename = payload.get("filename", "")
    try:
        return restore_database_backup(filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
