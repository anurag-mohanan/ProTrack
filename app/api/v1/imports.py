from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.auth_deps import require_roles
from app.api.deps import get_db
from app.schemas.historical_import import (
    ImportJobProgress,
    ImportRunRequest,
    ImportRunResponse,
    ImportUploadResponse,
)
from app.services.historical_import_service import (
    analyze_upload,
    error_log_to_csv,
    run_import,
    save_upload,
)
from app.services.import_job_store import import_job_store

router = APIRouter(
    prefix="/imports/historical-projects",
    tags=["imports"],
    dependencies=[Depends(require_roles("Admin"))],
)


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_historical_projects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )

    suffix = file.filename.lower().split(".")[-1]
    if suffix not in {"xlsx", "xlsm"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx and .xlsm files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    upload_id = str(uuid4())
    try:
        save_upload(upload_id, file.filename, content)
        return analyze_upload(db, upload_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/upload/{upload_id}/preview", response_model=ImportUploadResponse)
def preview_upload(upload_id: str, db: Session = Depends(get_db)):
    try:
        return analyze_upload(db, upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _execute_import_job(
    job_id: str,
    upload_id: str,
    *,
    dry_run: bool,
    duplicate_action,
) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        import_job_store.mark_running(job_id)

        def progress_callback(processed: int, total: int) -> None:
            import_job_store.update_progress(
                job_id,
                processed_rows=processed,
                total_rows=total,
            )

        summary, error_log = run_import(
            db,
            upload_id,
            dry_run=dry_run,
            duplicate_action=duplicate_action,
            progress_callback=progress_callback,
        )
        import_job_store.complete(
            job_id,
            summary=summary,
            error_log=error_log,
            dry_run=dry_run,
        )
    except Exception as exc:
        import_job_store.fail(job_id, str(exc))
    finally:
        db.close()


@router.post("/run", response_model=ImportRunResponse)
def run_historical_import(
    payload: ImportRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        analysis = analyze_upload(db, payload.upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired.",
        ) from exc

    job_id = import_job_store.create_job(analysis.total_rows)
    background_tasks.add_task(
        _execute_import_job,
        job_id,
        payload.upload_id,
        dry_run=payload.dry_run,
        duplicate_action=payload.duplicate_action,
    )
    return ImportRunResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=ImportJobProgress)
def get_import_job(job_id: str):
    job = import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found.",
        )
    return job


@router.get("/jobs/{job_id}/errors.csv")
def download_import_errors(job_id: str):
    job = import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found.",
        )
    csv_content = error_log_to_csv(job.error_log)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import-errors-{job_id}.csv"'},
    )
