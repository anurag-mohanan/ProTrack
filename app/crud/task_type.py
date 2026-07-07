import logging
from typing import override
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.crud.base import CRUDBase
from app.models.models import Stream, TaskType
from app.schemas.organization import TaskTypeCreate, TaskTypeUpdate

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    return name.strip()


def _find_duplicate(
    db: Session,
    *,
    stream_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> TaskType | None:
    stmt = select(TaskType).where(
        TaskType.stream_id == stream_id,
        func.lower(TaskType.name) == name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(TaskType.id != exclude_id)
    return db.scalar(stmt)


def _get_stream_or_error(db: Session, stream_id: UUID) -> Stream:
    stream = db.get(Stream, stream_id)
    if stream is None:
        raise ProTrackValidationError(
            "Selected stream does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if not stream.is_active:
        raise ProTrackValidationError(
            "Selected stream is inactive. Choose an active stream or reactivate it first.",
        )
    return stream


def _integrity_error_message(exc: IntegrityError) -> str:
    raw = str(exc.orig).lower() if exc.orig is not None else str(exc).lower()
    if "task_types" in raw and ("unique" in raw or "stream_id" in raw):
        return "A task type with this name already exists for the selected stream."
    if "foreign key" in raw and "stream" in raw:
        return "Selected stream does not exist."
    return "Unable to save task type due to a database constraint."


class CRUDTaskType(CRUDBase[TaskType, TaskTypeCreate, TaskTypeUpdate]):
    def _validate_create_payload(self, db: Session, obj_in: TaskTypeCreate) -> dict:
        payload = obj_in.model_dump()
        logger.info("Validating task type create payload: %s", payload)

        name = _normalize_name(str(payload.get("name", "")))
        if not name:
            raise ProTrackValidationError("Name is required.")

        stream_id = payload["stream_id"]
        _get_stream_or_error(db, stream_id)

        if _find_duplicate(db, stream_id=stream_id, name=name) is not None:
            raise ProTrackValidationError(
                "A task type with this name already exists for the selected stream.",
                status_code=status.HTTP_409_CONFLICT,
            )

        payload["name"] = name
        return payload

    @override
    def create(self, db: Session, *, obj_in: TaskTypeCreate) -> TaskType:
        create_data = self._validate_create_payload(db, obj_in)
        db_obj = TaskType(**create_data)
        db.add(db_obj)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            message = _integrity_error_message(exc)
            logger.warning(
                "Task type create failed integrity check: %s payload=%s",
                exc,
                create_data,
                exc_info=True,
            )
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "does not exist" in message
                else status.HTTP_409_CONFLICT
            )
            raise ProTrackValidationError(message, status_code=status_code) from exc
        except Exception:
            db.rollback()
            logger.exception("Unexpected error creating task type payload=%s", create_data)
            raise

        db.refresh(db_obj)
        logger.info("Created task type id=%s name=%s stream_id=%s", db_obj.id, db_obj.name, db_obj.stream_id)
        return db_obj

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: TaskType,
        obj_in: TaskTypeUpdate | dict,
    ) -> TaskType:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        logger.info("Updating task type id=%s payload=%s", db_obj.id, update_data)

        stream_id = update_data.get("stream_id", db_obj.stream_id)
        if "stream_id" in update_data:
            _get_stream_or_error(db, stream_id)

        if "name" in update_data and update_data["name"] is not None:
            name = _normalize_name(str(update_data["name"]))
            if not name:
                raise ProTrackValidationError("Name is required.")
            update_data["name"] = name
        else:
            name = db_obj.name

        if _find_duplicate(db, stream_id=stream_id, name=name, exclude_id=db_obj.id) is not None:
            raise ProTrackValidationError(
                "A task type with this name already exists for the selected stream.",
                status_code=status.HTTP_409_CONFLICT,
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            message = _integrity_error_message(exc)
            logger.warning(
                "Task type update failed integrity check id=%s: %s payload=%s",
                db_obj.id,
                exc,
                update_data,
                exc_info=True,
            )
            status_code = (
                status.HTTP_404_NOT_FOUND
                if "does not exist" in message
                else status.HTTP_409_CONFLICT
            )
            raise ProTrackValidationError(message, status_code=status_code) from exc
        except Exception:
            db.rollback()
            logger.exception("Unexpected error updating task type id=%s payload=%s", db_obj.id, update_data)
            raise

        db.refresh(db_obj)
        return db_obj


task_type = CRUDTaskType(TaskType)
