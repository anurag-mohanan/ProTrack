from uuid import UUID

from app.api.auth_deps import require_roles
from app.api.deps import APIRouter, Depends, HTTPException, Session, get_db, status
from app.crud.foundation import (
    department,
    get_or_create_company_settings,
    get_or_create_file_path_settings,
    get_or_create_notification_settings,
    holiday,
    list_contact_types,
    list_disciplines,
    list_skills,
    list_user_skills,
    replace_user_skills,
    update_company_settings,
    update_file_path_settings,
    update_notification_settings,
)
from app.schemas.settings import (
    CompanySettingsRead,
    CompanySettingsUpdate,
    ContactTypeRead,
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    EngineeringDisciplineRead,
    FilePathSettingsRead,
    FilePathSettingsUpdate,
    HolidayCreate,
    HolidayRead,
    HolidayUpdate,
    NotificationSettingsRead,
    NotificationSettingsUpdate,
    SkillRead,
    UserSkillCreate,
    UserSkillRead,
)

router = APIRouter(prefix="/settings", tags=["settings"])
admin_access = [Depends(require_roles("Admin", "Engineering Manager"))]


@router.get("/company", response_model=CompanySettingsRead)
def get_company_settings(db: Session = Depends(get_db)):
    return get_or_create_company_settings(db)


@router.patch("/company", response_model=CompanySettingsRead, dependencies=admin_access)
def patch_company_settings(payload: CompanySettingsUpdate, db: Session = Depends(get_db)):
    return update_company_settings(db, payload)


@router.get("/file-paths", response_model=FilePathSettingsRead)
def get_file_path_settings(db: Session = Depends(get_db)):
    return get_or_create_file_path_settings(db)


@router.patch("/file-paths", response_model=FilePathSettingsRead, dependencies=admin_access)
def patch_file_path_settings(payload: FilePathSettingsUpdate, db: Session = Depends(get_db)):
    return update_file_path_settings(db, payload)


@router.get("/notifications", response_model=NotificationSettingsRead)
def get_notification_settings(db: Session = Depends(get_db)):
    return get_or_create_notification_settings(db)


@router.patch(
    "/notifications",
    response_model=NotificationSettingsRead,
    dependencies=admin_access,
)
def patch_notification_settings(
    payload: NotificationSettingsUpdate, db: Session = Depends(get_db)
):
    return update_notification_settings(db, payload)


@router.get("/holidays", response_model=list[HolidayRead])
def list_holidays(db: Session = Depends(get_db)):
    return holiday.list(db)


@router.post("/holidays", response_model=HolidayRead, dependencies=admin_access)
def create_holiday(payload: HolidayCreate, db: Session = Depends(get_db)):
    return holiday.create(db, payload)


@router.patch("/holidays/{holiday_id}", response_model=HolidayRead, dependencies=admin_access)
def update_holiday(holiday_id: UUID, payload: HolidayUpdate, db: Session = Depends(get_db)):
    row = holiday.update(db, holiday_id, payload)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    return row


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=admin_access)
def delete_holiday(holiday_id: UUID, db: Session = Depends(get_db)):
    if not holiday.delete(db, holiday_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(db: Session = Depends(get_db)):
    return department.list(db)


@router.post("/departments", response_model=DepartmentRead, dependencies=admin_access)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    return department.create(db, payload)


@router.patch("/departments/{department_id}", response_model=DepartmentRead, dependencies=admin_access)
def update_department(
    department_id: UUID, payload: DepartmentUpdate, db: Session = Depends(get_db)
):
    row = department.update(db, department_id, payload)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return row


@router.get("/contact-types", response_model=list[ContactTypeRead])
def get_contact_types(db: Session = Depends(get_db)):
    return list_contact_types(db)


@router.get("/skills", response_model=list[SkillRead])
def get_skills(db: Session = Depends(get_db)):
    return list_skills(db)


@router.get("/disciplines", response_model=list[EngineeringDisciplineRead])
def get_disciplines(db: Session = Depends(get_db)):
    return list_disciplines(db)


@router.get("/users/{user_id}/skills", response_model=list[UserSkillRead])
def get_user_skills(user_id: UUID, db: Session = Depends(get_db)):
    rows = list_user_skills(db, user_id)
    return [
        UserSkillRead(
            id=row.id,
            user_id=row.user_id,
            skill_id=row.skill_id,
            skill_name=row.skill.name if row.skill else None,
            proficiency=row.proficiency,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.put("/users/{user_id}/skills", response_model=list[UserSkillRead], dependencies=admin_access)
def set_user_skills(
    user_id: UUID,
    payload: list[UserSkillCreate],
    db: Session = Depends(get_db),
):
    rows = replace_user_skills(db, user_id, payload)
    return [
        UserSkillRead(
            id=row.id,
            user_id=row.user_id,
            skill_id=row.skill_id,
            skill_name=row.skill.name if row.skill else None,
            proficiency=row.proficiency,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
