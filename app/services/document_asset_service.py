"""Document asset storage — local backend with S3-ready keys (R4 DMS metadata)."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config as app_config
from app.core.uploads import enforce_upload_size
from app.models.enterprise import DocumentAsset
from app.models.models import User


def _documents_root() -> Path:
    root = Path(getattr(app_config, "UPLOAD_DIR", Path("uploads"))) / "documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_document(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    filename: str,
    content: bytes,
    content_type: str | None,
    uploaded_by: User | None,
    title: str | None = None,
    notes: str | None = None,
) -> DocumentAsset:
    enforce_upload_size(content)
    asset_id = uuid.uuid4()
    safe_name = Path(filename).name or "upload.bin"
    storage_key = f"{entity_type}/{entity_id}/{asset_id}_{safe_name}"
    target = _documents_root() / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()

    row = DocumentAsset(
        id=asset_id,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title or safe_name,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(content),
        storage_backend="local",
        storage_key=storage_key,
        checksum=checksum,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
        notes=notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_documents(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> list[DocumentAsset]:
    stmt = select(DocumentAsset).order_by(DocumentAsset.created_at.desc())
    if entity_type:
        stmt = stmt.where(DocumentAsset.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(DocumentAsset.entity_id == entity_id)
    return list(db.scalars(stmt.limit(200)).all())


def resolve_local_path(asset: DocumentAsset) -> Path | None:
    if asset.storage_backend != "local":
        return None
    path = _documents_root() / asset.storage_key
    return path if path.is_file() else None
