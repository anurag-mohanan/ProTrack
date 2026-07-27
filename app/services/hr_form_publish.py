"""Shared publish helpers for HR form documents (onboarding, exit, performance)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.exceptions import ProTrackValidationError
from app.models.models import User


PUBLISHED_DELETE_MESSAGE = (
    "This document is published and cannot be deleted. "
    "Unpublish is not available — contact an administrator if a correction is required."
)


def is_published(row: Any) -> bool:
    return bool(getattr(row, "is_published", False))


def assert_can_delete(row: Any, *, document_label: str = "document") -> None:
    if is_published(row):
        raise ProTrackValidationError(
            f"Published {document_label} cannot be deleted. "
            "Once published, the record is locked for audit."
        )


def publish_document(row: Any, *, user: User) -> Any:
    if is_published(row):
        raise ProTrackValidationError("This document is already published.")
    row.is_published = True
    row.published_at = datetime.utcnow()
    row.published_by_id = user.id
    return row
