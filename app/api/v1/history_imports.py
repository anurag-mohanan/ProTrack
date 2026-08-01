"""CSV history import packs — employment, compensation, expenses, customers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.core.uploads import enforce_upload_size
from app.services import history_import_service

router = APIRouter(
    prefix="/imports/history",
    tags=["history-imports"],
    dependencies=[Depends(require_roles("Admin"))],
)


class HistoryPackRead(BaseModel):
    id: str
    title: str
    description: str
    template: str | None = None
    columns: list[str] = Field(default_factory=list)
    href: str | None = None
    note: str | None = None


class HistoryImportResult(BaseModel):
    pack: str
    dry_run: bool
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@router.get("/packs", response_model=list[HistoryPackRead])
def list_history_packs():
    return [HistoryPackRead(**p) for p in history_import_service.list_packs()]


@router.get("/packs/{pack_id}/template")
def download_template(pack_id: str):
    try:
        csv_text = history_import_service.template_csv(pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(
        csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{pack_id}_history_template.csv"'
        },
    )


@router.post("/packs/{pack_id}/import", response_model=HistoryImportResult)
async def import_history_pack(
    pack_id: str,
    file: UploadFile = File(...),
    dry_run: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    if pack_id not in history_import_service.IMPORTERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import pack not found or not CSV-backed",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    enforce_upload_size(content)
    try:
        result = history_import_service.run_pack(
            db, pack_id, content, dry_run=dry_run
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not dry_run:
        db.commit()
    return HistoryImportResult(
        pack=result.pack,
        dry_run=result.dry_run,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
        warnings=result.warnings,
    )
