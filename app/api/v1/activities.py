from uuid import UUID

from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.models.models import Activity, Milestone, Project, TimesheetEntry, User
from app.schemas.timesheet import ActivityRead

router = APIRouter(
    prefix="/activities",
    tags=["activities"],
    dependencies=[Depends(get_current_user)],
)


def _activity_to_read(db: Session, activity: Activity) -> ActivityRead:
    user_name = None
    if activity.user_id is not None:
        user = db.get(User, activity.user_id)
        if user is not None:
            user_name = f"{user.first_name} {user.last_name}"
    return ActivityRead(
        id=activity.id,
        user_id=activity.user_id,
        user_name=user_name,
        entity_type=activity.entity_type,
        entity_id=activity.entity_id,
        action=activity.action,
        old_value=activity.old_value,
        new_value=activity.new_value,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


def _project_activity_query(db: Session, project_id: UUID):
    milestone_ids = db.scalars(
        select(Milestone.id).where(Milestone.project_id == project_id)
    ).all()
    timesheet_ids = db.scalars(
        select(TimesheetEntry.timesheet_id).where(
            TimesheetEntry.project_id == project_id
        )
    ).all()
    entity_ids = {project_id, *milestone_ids, *timesheet_ids}
    return (
        select(Activity)
        .where(Activity.entity_id.in_(entity_ids))
        .order_by(Activity.created_at.desc())
    )


@router.get("", response_model=list[ActivityRead])
def list_activities(
    project_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if project_id is not None:
        query = _project_activity_query(db, project_id)
    else:
        query = select(Activity).order_by(Activity.created_at.desc())
    rows = db.scalars(query.offset(skip).limit(limit)).all()
    return [_activity_to_read(db, row) for row in rows]


@router.get("/project/{project_id}", response_model=list[ActivityRead])
def project_activities(
    project_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    _ = db.get(Project, project_id)
    rows = db.scalars(_project_activity_query(db, project_id).limit(limit)).all()
    return [_activity_to_read(db, row) for row in rows]
