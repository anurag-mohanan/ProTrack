from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.schemas.system import SystemHealthRead
from app.services.system_health_service import get_system_health

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthRead)
def read_system_health(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles("Admin")),
):
    return get_system_health(db)
