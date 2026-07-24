"""R4 documents API — DMS metadata + local upload path."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.uploads import enforce_upload_size
from app.models.enterprise import DocumentAsset
from app.models.models import User
from app.schemas.enterprise import DocumentAssetRead
from app.services.document_asset_service import list_documents, resolve_local_path, store_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentAssetRead])
def list_document_assets(
    entity_type: str | None = Query(None),
    entity_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return list_documents(db, entity_type=entity_type, entity_id=entity_id)


@router.post("", response_model=DocumentAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_document_asset(
    entity_type: str = Form(...),
    entity_id: UUID = Form(...),
    title: str | None = Form(None),
    notes: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    enforce_upload_size(content)
    row = store_document(
        db,
        entity_type=entity_type.strip().lower(),
        entity_id=entity_id,
        filename=file.filename or "upload.bin",
        content=content,
        content_type=file.content_type,
        uploaded_by=current_user,
        title=title,
        notes=notes,
    )
    return row


@router.get("/{document_id}/download")
def download_document_asset(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    asset = db.get(DocumentAsset, document_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    path = resolve_local_path(asset)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not available on this storage backend",
        )
    return FileResponse(
        path,
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.filename,
    )
