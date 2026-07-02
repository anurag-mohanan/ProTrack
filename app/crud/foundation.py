"""CRUD helpers for Phase 7 foundation settings."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import (
    BrandingSettings,
    CompanySettings,
    ContactType,
    Department,
    EngineeringDiscipline,
    FilePathSettings,
    Holiday,
    NotificationSettings,
    Skill,
    UserSkill,
)
from app.schemas.settings import (
    BrandingSettingsUpdate,
    CompanySettingsUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    FilePathSettingsUpdate,
    HolidayCreate,
    HolidayUpdate,
    NotificationSettingsUpdate,
    UserSkillCreate,
)


def get_or_create_company_settings(db: Session) -> CompanySettings:
    settings = db.scalar(select(CompanySettings).limit(1))
    if settings is None:
        settings = CompanySettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_company_settings(
    db: Session, payload: CompanySettingsUpdate
) -> CompanySettings:
    settings = get_or_create_company_settings(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_or_create_file_path_settings(db: Session) -> FilePathSettings:
    settings = db.scalar(select(FilePathSettings).limit(1))
    if settings is None:
        settings = FilePathSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_file_path_settings(
    db: Session, payload: FilePathSettingsUpdate
) -> FilePathSettings:
    settings = get_or_create_file_path_settings(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_or_create_notification_settings(db: Session) -> NotificationSettings:
    settings = db.scalar(select(NotificationSettings).limit(1))
    if settings is None:
        settings = NotificationSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_notification_settings(
    db: Session, payload: NotificationSettingsUpdate
) -> NotificationSettings:
    settings = get_or_create_notification_settings(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


class CRUDHoliday:
    def list(self, db: Session) -> list[Holiday]:
        return db.scalars(select(Holiday).order_by(Holiday.holiday_date)).all()

    def create(self, db: Session, obj_in: HolidayCreate) -> Holiday:
        row = Holiday(**obj_in.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update(self, db: Session, record_id: UUID, obj_in: HolidayUpdate) -> Holiday | None:
        row = db.get(Holiday, record_id)
        if row is None:
            return None
        for key, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def delete(self, db: Session, record_id: UUID) -> bool:
        row = db.get(Holiday, record_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


class CRUDDepartment:
    def list(self, db: Session, *, active_only: bool = False) -> list[Department]:
        stmt = select(Department).order_by(Department.name)
        if active_only:
            stmt = stmt.where(Department.is_active.is_(True))
        return db.scalars(stmt).all()

    def create(self, db: Session, obj_in: DepartmentCreate) -> Department:
        row = Department(**obj_in.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update(
        self, db: Session, record_id: UUID, obj_in: DepartmentUpdate
    ) -> Department | None:
        row = db.get(Department, record_id)
        if row is None:
            return None
        for key, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def list_contact_types(db: Session) -> list[ContactType]:
    return db.scalars(
        select(ContactType).where(ContactType.is_active.is_(True)).order_by(ContactType.name)
    ).all()


def list_skills(db: Session) -> list[Skill]:
    return db.scalars(
        select(Skill).where(Skill.is_active.is_(True)).order_by(Skill.name)
    ).all()


def list_disciplines(db: Session) -> list[EngineeringDiscipline]:
    return db.scalars(
        select(EngineeringDiscipline)
        .where(EngineeringDiscipline.is_active.is_(True))
        .order_by(EngineeringDiscipline.name)
    ).all()


def list_user_skills(db: Session, user_id: UUID) -> list[UserSkill]:
    return db.scalars(select(UserSkill).where(UserSkill.user_id == user_id)).all()


def replace_user_skills(
    db: Session, user_id: UUID, skills: list[UserSkillCreate]
) -> list[UserSkill]:
    existing = db.scalars(select(UserSkill).where(UserSkill.user_id == user_id)).all()
    for row in existing:
        db.delete(row)
    created: list[UserSkill] = []
    for item in skills:
        row = UserSkill(
            user_id=user_id,
            skill_id=item.skill_id,
            proficiency=item.proficiency,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return created


holiday = CRUDHoliday()
department = CRUDDepartment()


def get_or_create_branding_settings(db: Session) -> BrandingSettings:
    settings = db.scalar(select(BrandingSettings).limit(1))
    if settings is None:
        from app.db.phase9_schema_sync import DEFAULT_BRANDING

        settings = BrandingSettings(**DEFAULT_BRANDING)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_branding_settings(
    db: Session, payload: BrandingSettingsUpdate
) -> BrandingSettings:
    settings = get_or_create_branding_settings(db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def restore_default_branding_settings(db: Session) -> BrandingSettings:
    from app.db.phase9_schema_sync import DEFAULT_BRANDING

    settings = get_or_create_branding_settings(db)
    for key, value in DEFAULT_BRANDING.items():
        setattr(settings, key, value)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings
