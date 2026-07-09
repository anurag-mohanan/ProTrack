from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.core.password_policy import PASSWORD_REQUIREMENTS_MESSAGE
from app.models.enums import ActivityAction, EntityType
from app.models.models import User
from app.schemas.operations import (
    DeveloperDiagnosticsSummary,
    DiagnosticsReport,
    HealthSnapshotPoint,
    LogLine,
    OperationsCenterSnapshot,
    ReleaseValidationReport,
)
from app.schemas.system import SystemHealthRead
from app.services.activity_service import log_activity
from app.services.backup_service import create_database_backup, list_database_backups, restore_database_backup
from app.services.health_history_store import get_history
from app.services.operations_center_service import (
    get_developer_diagnostics_summary,
    get_operations_snapshot,
    optimize_database,
    run_diagnostics,
    run_integrity_check,
    run_release_validation,
    run_maintenance_action,
    tail_logs,
)
from app.services.system_health_service import get_system_health

router = APIRouter(prefix="/system", tags=["system"])
admin = Depends(require_roles("Admin"))
ops_read = Depends(require_roles("Admin"))


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
    current_user: User = Depends(require_roles("Admin")),
    _admin=admin,
):
    result = run_integrity_check(db)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.settings,
        entity_id=current_user.id,
        action=ActivityAction.settings_updated,
        new_value={"maintenance_action": "integrity_check", "result": result},
    )
    return {"status": "ok" if result.lower() == "ok" else "warning", "result": result}


@router.post("/operations/optimize")
def run_db_optimize(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    _admin=admin,
):
    message = optimize_database(db)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.settings,
        entity_id=current_user.id,
        action=ActivityAction.settings_updated,
        new_value={"maintenance_action": "optimize_database", "message": message},
    )
    return {"status": "ok", "message": message}


@router.post("/operations/maintenance")
def run_maintenance(
    payload: dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    _admin=admin,
):
    action = payload.get("action", "")
    try:
        result = run_maintenance_action(action, db)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.settings,
            entity_id=current_user.id,
            action=ActivityAction.settings_updated,
            new_value={"maintenance_action": action, "status": result.get("status")},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/diagnostics/summary", response_model=DeveloperDiagnosticsSummary)
def read_developer_diagnostics_summary(
    db: Session = Depends(get_db),
    _admin=admin,
):
    return get_developer_diagnostics_summary(db)


@router.post("/diagnostics/release-validation", response_model=ReleaseValidationReport)
def run_diagnostics_release_validation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    report = run_release_validation(db)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.settings,
        entity_id=current_user.id,
        action=ActivityAction.settings_updated,
        new_value={
            "maintenance_action": "run_release_validation",
            "status": report.status,
            "critical": report.critical,
            "warnings": report.warnings,
        },
    )
    return report


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
def create_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    _admin=admin,
):
    try:
        result = create_database_backup()
        log_activity(
            db=db,
            user=current_user,
            entity_type=EntityType.settings,
            entity_id=current_user.id,
            action=ActivityAction.settings_updated,
            new_value={"maintenance_action": "create_backup", "filename": result.get("filename")},
        )
        return result
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/backups/restore")
def restore_backup(
    payload: dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    _admin=admin,
):
    filename = payload.get("filename", "")
    try:
        result = restore_database_backup(filename)
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.settings,
            entity_id=current_user.id,
            action=ActivityAction.settings_updated,
            new_value={"maintenance_action": "restore_backup", "filename": filename},
        )
        return result
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
