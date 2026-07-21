"""Shared helpers for validating uploaded file content."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import MAX_UPLOAD_BYTES


def enforce_upload_size(content: bytes, *, max_bytes: int | None = None) -> None:
    """Reject an upload whose body exceeds the configured cap.

    A global request-body middleware provides the primary DoS protection; this
    gives callers a clean, specific 413 for oversized files.
    """
    limit = max_bytes if max_bytes is not None else MAX_UPLOAD_BYTES
    if len(content) > limit:
        mb = limit / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds the maximum allowed size of {mb:.0f} MB.",
        )
