from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.core.password_policy import PASSWORD_REQUIREMENTS_MESSAGE
from app.schemas.system import SystemHealthRead
from app.services.backup_service import create_database_backup, list_database_backups, restore_database_backup
from app.services.system_health_service import get_system_health

router = APIRouter(prefix="/system", tags=["system"])
admin = Depends(require_roles("Admin"))


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
