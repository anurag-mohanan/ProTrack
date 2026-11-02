from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, override
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse
from app.crud.base import CRUDBase
from app.models.models import (
    Customer,
    Project,
    ProjectTemplate,
    ProjectTemplateMilestone,
    ProjectType,
)
from app.schemas.templates import (
    ProjectTemplateCreate,
    ProjectTemplateMilestoneCreate,
    ProjectTemplateUpdate,
)
from app.services.project_template_service import (
    clear_default_for_type,
    template_is_in_use,
)
from app.services.scheduling_service import dump_id_list, find_dependency_cycle, parse_id_list


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_template_references(
    db: Session,
    *,
    project_type_id: UUID,
    customer_id: UUID | None,
) -> None:
    project_type = db.get(ProjectType, project_type_id)
    if project_type is None or not project_type.is_active:
        raise ProTrackValidationError(
            "project_type_id must reference an active project type"
        )
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None or not customer.is_active:
            raise ProTrackValidationError(
                "customer_id must reference an active customer"
            )


def _milestone_values(milestone: ProjectTemplateMilestoneCreate, *, index: int) -> dict[str, Any]:
    return {
        "milestone_name": milestone.milestone_name,
        "description": milestone.description,
        "sort_order": milestone.sort_order or index,
        "default_due_offset_days": milestone.default_due_offset_days,
        "is_required": milestone.is_required,
        "is_visible": milestone.is_visible,
        "project_stage": milestone.project_stage,
        "estimated_hours": milestone.estimated_hours,
        "assigned_role": milestone.assigned_role,
        "default_assigned_user_id": milestone.default_assigned_user_id,
    }


def _validate_milestone_payload(milestones: list[ProjectTemplateMilestoneCreate]) -> None:
    names: set[str] = set()
    keys: set[str] = set()
    for milestone in milestones:
        lowered = milestone.milestone_name.strip().lower()
        if lowered in names:
            raise ProTrackValidationError(
                f"Milestone '{milestone.milestone_name}' appears more than once in this template"
            )
        names.add(lowered)
        key = str(milestone.id) if milestone.id else milestone.client_key
        if key:
            if key in keys:
                raise ProTrackValidationError("Each milestone row needs a unique id or client key")
            keys.add(key)


def _sync_milestones(
    db: Session,
    template: ProjectTemplate,
    milestones: list[ProjectTemplateMilestoneCreate],
    *,
    keep_ids: bool,
    lineage_from: dict[UUID, UUID] | None = None,
) -> None:
    """Upsert milestones by id, delete removed rows, then resolve dependencies.

    ``keep_ids=False`` (new version / new template) always inserts fresh rows and
    maps incoming ids to the new rows so dependencies are preserved.
    ``lineage_from`` maps source row ids to their lineage so a new version keeps
    each milestone's stable identity across versions; other new rows start a lineage.
    """
    _validate_milestone_payload(milestones)
    existing = {row.id: row for row in template.milestones} if keep_ids else {}
    incoming_ids = {item.id for item in milestones if item.id is not None}
    for row_id, row in list(existing.items()):
        if row_id not in incoming_ids:
            db.delete(row)
            existing.pop(row_id)
    db.flush()

    key_to_row: dict[str, ProjectTemplateMilestone] = {}
    rows_in_order: list[tuple[ProjectTemplateMilestoneCreate, ProjectTemplateMilestone]] = []
    for index, item in enumerate(milestones, start=1):
        values = _milestone_values(item, index=index)
        row = existing.get(item.id) if item.id is not None else None
        if row is None:
            row = ProjectTemplateMilestone(project_template_id=template.id, **values)
            if lineage_from and item.id is not None:
                row.lineage_id = lineage_from.get(item.id)
            db.add(row)
        else:
            for field, value in values.items():
                setattr(row, field, value)
        rows_in_order.append((item, row))
        if item.id is not None:
            key_to_row[str(item.id)] = row
        if item.client_key:
            key_to_row[item.client_key] = row
    db.flush()
    for _item, row in rows_in_order:
        if row.lineage_id is None:
            row.lineage_id = row.id

    dependency_map: dict[str, list[str]] = {}
    for item, row in rows_in_order:
        resolved: list[str] = []
        for ref in item.depends_on:
            target = key_to_row.get(str(ref))
            if target is None:
                raise ProTrackValidationError(
                    f"'{item.milestone_name}' depends on a milestone that is not in this template"
                )
            if target is row:
                raise ProTrackValidationError(
                    f"'{item.milestone_name}' cannot depend on itself"
                )
            resolved.append(str(target.id))
        row.depends_on_ids = dump_id_list(resolved)
        dependency_map[str(row.id)] = resolved
    if find_dependency_cycle(dependency_map):
        raise ProTrackValidationError("Milestone dependencies form a loop; remove one of the links")


def _milestone_signature(rows: list[ProjectTemplateMilestone]) -> list[tuple]:
    ordered = sorted(rows, key=lambda row: row.sort_order)
    position = {str(row.id): index for index, row in enumerate(ordered)}
    return [
        (
            row.milestone_name,
            row.description or None,
            index + 1,
            row.default_due_offset_days,
            bool(row.is_required),
            bool(row.is_visible),
            row.project_stage.value if row.project_stage else None,
            Decimal(str(row.estimated_hours)) if row.estimated_hours is not None else None,
            row.assigned_role or None,
            row.default_assigned_user_id,
            tuple(sorted(position.get(dep, -1) for dep in parse_id_list(row.depends_on_ids))),
        )
        for index, row in enumerate(ordered)
    ]


def _payload_signature(
    template: ProjectTemplate, milestones: list[ProjectTemplateMilestoneCreate]
) -> list[tuple]:
    existing_ids = {str(row.id) for row in template.milestones}
    keyed = {
        (str(item.id) if item.id else item.client_key): index
        for index, item in enumerate(milestones)
        if item.id or item.client_key
    }
    signature = []
    for index, item in enumerate(milestones):
        deps = []
        for ref in item.depends_on:
            deps.append(keyed.get(str(ref), -1 if str(ref) not in existing_ids else -2))
        signature.append(
            (
                item.milestone_name,
                item.description or None,
                index + 1,
                item.default_due_offset_days,
                bool(item.is_required),
                bool(item.is_visible),
                item.project_stage.value if item.project_stage else None,
                Decimal(str(item.estimated_hours)) if item.estimated_hours is not None else None,
                item.assigned_role or None,
                item.default_assigned_user_id,
                tuple(sorted(deps)),
            )
        )
    return signature


def _family_id(template: ProjectTemplate) -> UUID:
    return template.template_family_id or template.id


class CRUDProjectTemplate(
    CRUDBase[ProjectTemplate, ProjectTemplateCreate, ProjectTemplateUpdate]
):
    def get_with_milestones(
        self, db: Session, record_id: UUID
    ) -> ProjectTemplate | None:
        return db.scalar(
            select(ProjectTemplate)
            .options(
                selectinload(ProjectTemplate.milestones),
                selectinload(ProjectTemplate.project_type),
                selectinload(ProjectTemplate.customer),
            )
            .where(ProjectTemplate.id == record_id)
        )

    def family_versions(self, db: Session, template: ProjectTemplate) -> list[ProjectTemplate]:
        family_id = _family_id(template)
        return list(
            db.scalars(
                select(ProjectTemplate)
                .options(selectinload(ProjectTemplate.milestones))
                .where(
                    or_(
                        ProjectTemplate.template_family_id == family_id,
                        ProjectTemplate.id == family_id,
                    )
                )
                .order_by(ProjectTemplate.version.desc())
            ).all()
        )

    def version_count(self, db: Session, template: ProjectTemplate) -> int:
        family_id = _family_id(template)
        return int(
            db.scalar(
                select(func.count())
                .select_from(ProjectTemplate)
                .where(
                    or_(
                        ProjectTemplate.template_family_id == family_id,
                        ProjectTemplate.id == family_id,
                    )
                )
            )
            or 1
        )

    @staticmethod
    def _apply_list_filters(
        stmt,
        *,
        search: str | None = None,
        customer_id: UUID | None = None,
        project_type_id: UUID | None = None,
        scope: str | None = None,
        include_versions: bool = False,
    ):
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                ProjectTemplate.name.ilike(term)
                | ProjectTemplate.description.ilike(term)
            )
        if customer_id is not None:
            stmt = stmt.where(ProjectTemplate.customer_id == customer_id)
        if project_type_id is not None:
            stmt = stmt.where(ProjectTemplate.project_type_id == project_type_id)
        normalized_scope = (scope or "all").strip().lower()
        if normalized_scope == "customer":
            stmt = stmt.where(ProjectTemplate.customer_id.is_not(None))
        elif normalized_scope == "general":
            stmt = stmt.where(ProjectTemplate.customer_id.is_(None))
        if not include_versions:
            # One row per family: the active version, else the newest one.
            other = aliased(ProjectTemplate)
            family = func.coalesce(ProjectTemplate.template_family_id, ProjectTemplate.id)
            other_family = func.coalesce(other.template_family_id, other.id)
            stmt = stmt.where(
                ~exists().where(
                    and_(
                        other_family == family,
                        other.id != ProjectTemplate.id,
                        or_(
                            and_(other.is_active.is_(True), ProjectTemplate.is_active.is_(False)),
                            and_(
                                other.is_active == ProjectTemplate.is_active,
                                other.version > ProjectTemplate.version,
                            ),
                        ),
                    )
                )
            )
        return stmt

    def get_multi_with_counts(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 500,
        search: str | None = None,
        customer_id: UUID | None = None,
        project_type_id: UUID | None = None,
        scope: str | None = None,
        include_versions: bool = False,
    ) -> list[tuple[ProjectTemplate, int, int]]:
        milestone_count = func.count(ProjectTemplateMilestone.id).label("milestone_count")
        stmt = (
            select(ProjectTemplate, milestone_count)
            .outerjoin(
                ProjectTemplateMilestone,
                ProjectTemplateMilestone.project_template_id == ProjectTemplate.id,
            )
            .options(
                selectinload(ProjectTemplate.project_type),
                selectinload(ProjectTemplate.customer),
            )
            .group_by(ProjectTemplate.id)
        )
        stmt = self._apply_list_filters(
            stmt,
            search=search,
            customer_id=customer_id,
            project_type_id=project_type_id,
            scope=scope,
            include_versions=include_versions,
        )
        rows = db.execute(
            stmt.order_by(ProjectTemplate.name, ProjectTemplate.version.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        template_ids = [template.id for template, _ in rows]
        usage_counts: dict[UUID, int] = {}
        if template_ids:
            usage_rows = db.execute(
                select(Project.project_template_id, func.count())
                .where(
                    Project.project_template_id.in_(template_ids),
                    Project.is_deleted.is_(False),
                )
                .group_by(Project.project_template_id)
            ).all()
            usage_counts = {
                template_id: int(count) for template_id, count in usage_rows if template_id
            }
        return [
            (template, int(count), usage_counts.get(template.id, 0))
            for template, count in rows
        ]

    def count_list(
        self,
        db: Session,
        *,
        search: str | None = None,
        customer_id: UUID | None = None,
        project_type_id: UUID | None = None,
        scope: str | None = None,
        include_versions: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(ProjectTemplate)
        stmt = self._apply_list_filters(
            stmt,
            search=search,
            customer_id=customer_id,
            project_type_id=project_type_id,
            scope=scope,
            include_versions=include_versions,
        )
        return int(db.scalar(stmt) or 0)

    def get_multi_paginated_with_counts(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 25,
        skip: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        customer_id: UUID | None = None,
        project_type_id: UUID | None = None,
        scope: str | None = None,
        include_versions: bool = False,
    ) -> PaginatedResponse[Any]:
        resolved_skip = skip if skip is not None else (page - 1) * page_size
        resolved_limit = limit if limit is not None else page_size
        resolved_page = (resolved_skip // resolved_limit) + 1 if resolved_limit else page
        total = self.count_list(
            db,
            search=search,
            customer_id=customer_id,
            project_type_id=project_type_id,
            scope=scope,
            include_versions=include_versions,
        )
        rows = self.get_multi_with_counts(
            db,
            skip=resolved_skip,
            limit=resolved_limit,
            search=search,
            customer_id=customer_id,
            project_type_id=project_type_id,
            scope=scope,
            include_versions=include_versions,
        )
        return PaginatedResponse.build(
            items=rows,
            total=total,
            page=resolved_page,
            page_size=resolved_limit,
        )

    def _deactivate_siblings(self, db: Session, template: ProjectTemplate) -> None:
        for sibling in self.family_versions(db, template):
            if sibling.id != template.id and sibling.is_active:
                sibling.is_active = False
                db.add(sibling)

    @override
    def create(
        self,
        db: Session,
        *,
        obj_in: ProjectTemplateCreate,
        created_by_id: UUID | None = None,
    ) -> ProjectTemplate:
        _validate_template_references(
            db,
            project_type_id=obj_in.project_type_id,
            customer_id=obj_in.customer_id,
        )
        if obj_in.is_active and not obj_in.milestones:
            raise ProTrackValidationError(
                "Active project templates must include at least one milestone"
            )
        try:
            if obj_in.is_default and obj_in.customer_id is None:
                clear_default_for_type(db, project_type_id=obj_in.project_type_id)

            data = obj_in.model_dump(exclude={"milestones"})
            db_obj = ProjectTemplate(
                **data,
                version=1,
                created_by_id=created_by_id,
                activated_at=_now() if obj_in.is_active else None,
            )
            db.add(db_obj)
            db.flush()
            db_obj.template_family_id = db_obj.id
            if obj_in.milestones:
                _sync_milestones(db, db_obj, obj_in.milestones, keep_ids=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(db_obj)
        return self.get_with_milestones(db, db_obj.id) or db_obj

    def _new_version(
        self,
        db: Session,
        *,
        source: ProjectTemplate,
        overrides: dict[str, object],
        milestones: list[ProjectTemplateMilestoneCreate] | None,
        activate: bool,
        created_by_id: UUID | None,
    ) -> ProjectTemplate:
        family_id = _family_id(source)
        latest = max((row.version for row in self.family_versions(db, source)), default=1)
        fields = {
            "name": source.name,
            "description": source.description,
            "project_type_id": source.project_type_id,
            "customer_id": source.customer_id,
            "default_team_id": source.default_team_id,
            "is_default": source.is_default,
            "scheduling_mode": source.scheduling_mode,
        }
        fields.update({key: value for key, value in overrides.items() if key in fields})
        revision = ProjectTemplate(
            **fields,
            is_active=activate,
            template_family_id=family_id,
            version=latest + 1,
            revision_note=overrides.get("revision_note"),  # type: ignore[arg-type]
            activated_at=_now() if activate else None,
            created_by_id=created_by_id,
        )
        db.add(revision)
        db.flush()
        if source.template_family_id is None:
            source.template_family_id = family_id
            db.add(source)
        if milestones is None:
            milestones = [
                ProjectTemplateMilestoneCreate(
                    id=row.id,
                    milestone_name=row.milestone_name,
                    description=row.description,
                    sort_order=row.sort_order,
                    default_due_offset_days=row.default_due_offset_days,
                    is_required=row.is_required,
                    is_visible=row.is_visible,
                    project_stage=row.project_stage,
                    estimated_hours=row.estimated_hours,
                    assigned_role=row.assigned_role,
                    default_assigned_user_id=row.default_assigned_user_id,
                    depends_on=parse_id_list(row.depends_on_ids),
                )
                for row in sorted(source.milestones, key=lambda item: item.sort_order)
            ]
        _sync_milestones(
            db,
            revision,
            milestones,
            keep_ids=False,
            lineage_from={row.id: row.lineage_id or row.id for row in source.milestones},
        )
        if activate:
            self._deactivate_siblings(db, revision)
        return revision

    def update_with_versioning(
        self,
        db: Session,
        *,
        db_obj: ProjectTemplate,
        obj_in: ProjectTemplateUpdate,
        updated_by_id: UUID | None = None,
    ) -> tuple[ProjectTemplate, bool]:
        """Apply an edit. Returns (template, created_new_version).

        Milestone changes on a version that projects already use are saved as a
        new active version; the old version stays untouched for those projects.
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        milestones_payload = update_data.pop("milestones", None)
        milestones = obj_in.milestones if milestones_payload is not None else None
        project_type_id = update_data.get("project_type_id", db_obj.project_type_id)
        customer_id = update_data.get("customer_id", db_obj.customer_id)
        if not isinstance(project_type_id, UUID):
            raise ProTrackValidationError("project_type_id must be a UUID")
        customer_uuid = customer_id if isinstance(customer_id, UUID) else None
        _validate_template_references(db, project_type_id=project_type_id, customer_id=customer_uuid)

        will_be_active = bool(update_data.get("is_active", db_obj.is_active))
        if milestones is not None and will_be_active and not milestones:
            raise ProTrackValidationError(
                "Active project templates must include at least one milestone"
            )

        try:
            if update_data.get("is_default") and customer_uuid is None:
                clear_default_for_type(
                    db, project_type_id=project_type_id, exclude_template_id=db_obj.id
                )
            milestones_changed = milestones is not None and _payload_signature(
                db_obj, milestones
            ) != _milestone_signature(list(db_obj.milestones))
            structural_change = milestones_changed or (
                "scheduling_mode" in update_data
                and update_data["scheduling_mode"] != db_obj.scheduling_mode
            )
            if structural_change and template_is_in_use(db, db_obj.id):
                revision = self._new_version(
                    db,
                    source=db_obj,
                    overrides=update_data,
                    milestones=milestones,
                    activate=will_be_active,
                    created_by_id=updated_by_id,
                )
                db.commit()
                return self.get_with_milestones(db, revision.id) or revision, True

            becoming_active = update_data.get("is_active") is True and not db_obj.is_active
            for field, value in update_data.items():
                setattr(db_obj, field, value)
            if becoming_active:
                db_obj.activated_at = _now()
                self._deactivate_siblings(db, db_obj)
            db.add(db_obj)
            db.flush()
            if milestones is not None and milestones_changed:
                _sync_milestones(db, db_obj, milestones, keep_ids=True)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return self.get_with_milestones(db, db_obj.id) or db_obj, False

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: ProjectTemplate,
        obj_in: ProjectTemplateUpdate | dict[str, object],
    ) -> ProjectTemplate:
        schema = (
            obj_in
            if isinstance(obj_in, ProjectTemplateUpdate)
            else ProjectTemplateUpdate.model_validate(obj_in)
        )
        template, _created = self.update_with_versioning(db, db_obj=db_obj, obj_in=schema)
        return template

    def create_revision(
        self,
        db: Session,
        *,
        template_id: UUID,
        revision_note: str | None,
        created_by_id: UUID | None = None,
    ) -> ProjectTemplate:
        source = self.get_with_milestones(db, template_id)
        if source is None:
            raise ProTrackValidationError("Project template not found")
        try:
            revision = self._new_version(
                db,
                source=source,
                overrides={"revision_note": revision_note},
                milestones=None,
                activate=False,
                created_by_id=created_by_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return self.get_with_milestones(db, revision.id) or revision

    @override
    def delete(self, db: Session, *, record_id: UUID) -> ProjectTemplate | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        if template_is_in_use(db, record_id):
            raise ProTrackValidationError(
                "Cannot delete a project template that is used by existing projects"
            )
        return super().delete(db, record_id=record_id)

    def duplicate(
        self, db: Session, *, template_id: UUID, created_by_id: UUID | None = None
    ) -> ProjectTemplate:
        source = self.get_with_milestones(db, template_id)
        if source is None:
            raise ProTrackValidationError("Project template not found")
        try:
            duplicate = ProjectTemplate(
                name=f"{source.name} (Copy)",
                description=source.description,
                project_type_id=source.project_type_id,
                customer_id=source.customer_id,
                default_team_id=source.default_team_id,
                is_default=False,
                is_active=True,
                version=1,
                scheduling_mode=source.scheduling_mode,
                activated_at=_now(),
                created_by_id=created_by_id,
            )
            db.add(duplicate)
            db.flush()
            duplicate.template_family_id = duplicate.id
            _sync_milestones(
                db,
                duplicate,
                [
                    ProjectTemplateMilestoneCreate(
                        id=row.id,
                        milestone_name=row.milestone_name,
                        description=row.description,
                        sort_order=row.sort_order,
                        default_due_offset_days=row.default_due_offset_days,
                        is_required=row.is_required,
                        is_visible=row.is_visible,
                        project_stage=row.project_stage,
                        estimated_hours=row.estimated_hours,
                        assigned_role=row.assigned_role,
                        default_assigned_user_id=row.default_assigned_user_id,
                        depends_on=parse_id_list(row.depends_on_ids),
                    )
                    for row in sorted(source.milestones, key=lambda item: item.sort_order)
                ],
                keep_ids=False,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(duplicate)
        return self.get_with_milestones(db, duplicate.id) or duplicate

    def deactivate(self, db: Session, *, template_id: UUID) -> ProjectTemplate:
        db_obj = self.get(db, template_id)
        if db_obj is None:
            raise ProTrackValidationError("Project template not found")
        db_obj.is_active = False
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def reactivate(self, db: Session, *, template_id: UUID) -> ProjectTemplate:
        """Activate this version; other versions of the family are deactivated."""
        db_obj = self.get_with_milestones(db, template_id)
        if db_obj is None:
            raise ProTrackValidationError("Project template not found")
        if not db_obj.milestones:
            raise ProTrackValidationError(
                "Active project templates must include at least one milestone"
            )
        db_obj.is_active = True
        db_obj.activated_at = _now()
        if db_obj.template_family_id is None:
            db_obj.template_family_id = db_obj.id
        self._deactivate_siblings(db, db_obj)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


project_template = CRUDProjectTemplate(ProjectTemplate)
