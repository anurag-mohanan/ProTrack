from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.models.models import TimesheetImportHistory, User
from app.schemas.historical_timesheet_import import (
    TimesheetImportHistoryDetail,
    TimesheetImportHistoryRead,
    TimesheetImportJobProgress,
    TimesheetImportResolveRequest,
    TimesheetImportRunRequest,
    TimesheetImportRunResponse,
    TimesheetImportUploadResponse,
    TimesheetImportValidateResponse,
)
from app.services.historical_timesheet_import_service import (
    ImportContext,
    analyze_upload,
    error_log_to_csv,
    get_import_history,
    list_import_history,
    load_resolutions,
    run_timesheet_import,
    save_resolutions,
    save_upload,
    validate_upload,
)
from app.services.timesheet_import_job_store import timesheet_import_job_store

router = APIRouter(
    prefix="/imports/historical-timesheets",
    tags=["imports"],
    dependencies=[Depends(require_roles("Admin"))],
)


@router.post("/upload", response_model=TimesheetImportUploadResponse)
async def upload_historical_timesheets(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required.",
        )

    suffix = file.filename.lower().split(".")[-1]
    if suffix not in {"xlsx", "xlsm", "csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx, .xlsm, and .csv files are supported.",
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


@router.get("/upload/{upload_id}/preview", response_model=TimesheetImportUploadResponse)
def preview_timesheet_upload(upload_id: str, db: Session = Depends(get_db)):
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


@router.post("/upload/{upload_id}/validate", response_model=TimesheetImportValidateResponse)
def validate_timesheet_upload(upload_id: str, db: Session = Depends(get_db)):
    try:
        return validate_upload(db, upload_id)
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


@router.post("/upload/{upload_id}/resolve")
def resolve_timesheet_upload(
    upload_id: str,
    payload: TimesheetImportResolveRequest,
    db: Session = Depends(get_db),
):
    try:
        analyze_upload(db, upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired.",
        ) from exc

    context = ImportContext(
        designer_resolution=payload.designer,
        duplicate_week_action=payload.duplicate_week_action,
        project_resolutions={r.row_number: r for r in payload.project_resolutions},
        customer_resolutions={r.row_number: r for r in payload.customer_resolutions},
        task_type_resolutions={r.row_number: r for r in payload.task_type_resolutions},
    )
    save_resolutions(upload_id, context)
    return {"status": "saved"}


def _build_context(payload: TimesheetImportRunRequest) -> ImportContext:
    stored = load_resolutions(payload.upload_id)
    context = ImportContext(
        designer_resolution=payload.designer or stored.designer_resolution,
        duplicate_week_action=payload.duplicate_week_action or stored.duplicate_week_action,
        project_resolutions={
            **stored.project_resolutions,
            **{r.row_number: r for r in payload.project_resolutions},
        },
        customer_resolutions={
            **stored.customer_resolutions,
            **{r.row_number: r for r in payload.customer_resolutions},
        },
        task_type_resolutions={
            **stored.task_type_resolutions,
            **{r.row_number: r for r in payload.task_type_resolutions},
        },
    )
    if payload.designer:
        save_resolutions(payload.upload_id, context)
    return context


def _execute_timesheet_import_job(
    job_id: str,
    upload_id: str,
    *,
    dry_run: bool,
    context: ImportContext,
    imported_by_id: UUID,
) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        timesheet_import_job_store.mark_running(job_id)

        def progress_callback(processed: int, total: int) -> None:
            timesheet_import_job_store.update_progress(
                job_id,
                processed_rows=processed,
                total_rows=total,
            )

        summary, error_log, history_id = run_timesheet_import(
            db,
            upload_id,
            dry_run=dry_run,
            context=context,
            imported_by_id=imported_by_id,
            progress_callback=progress_callback,
        )
        timesheet_import_job_store.complete(
            job_id,
            summary=summary,
            error_log=error_log,
            dry_run=dry_run,
            history_id=history_id,
        )
    except Exception as exc:
        timesheet_import_job_store.fail(job_id, str(exc))
    finally:
        db.close()


@router.post("/run", response_model=TimesheetImportRunResponse)
def run_historical_timesheet_import(
    payload: TimesheetImportRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        analysis = analyze_upload(db, payload.upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired.",
        ) from exc

    context = _build_context(payload)
    job_id = timesheet_import_job_store.create_job(analysis.total_rows)
    background_tasks.add_task(
        _execute_timesheet_import_job,
        job_id,
        payload.upload_id,
        dry_run=payload.dry_run,
        context=context,
        imported_by_id=current_user.id,
    )
    return TimesheetImportRunResponse(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=TimesheetImportJobProgress)
def get_timesheet_import_job(job_id: str):
    job = timesheet_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found.",
        )
    return job


@router.get("/jobs/{job_id}/errors.csv")
def download_timesheet_import_errors(job_id: str):
    job = timesheet_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found.",
        )
    csv_content = error_log_to_csv(job.error_log)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="timesheet-import-{job_id}.csv"'},
    )


@router.get("/history", response_model=list[TimesheetImportHistoryRead])
def get_timesheet_import_history(db: Session = Depends(get_db), limit: int = 50):
    records = list_import_history(db, limit=limit)
    result: list[TimesheetImportHistoryRead] = []
    for record in records:
        imported_by = db.get(User, record.imported_by_id)
        result.append(
            TimesheetImportHistoryRead(
                id=record.id,
                filename=record.filename,
                imported_by_name=(
                    f"{imported_by.first_name} {imported_by.last_name}" if imported_by else "Unknown"
                ),
                designer_name=record.designer_name,
                date_range_label=record.date_range_label,
                rows_imported=record.rows_imported,
                rows_failed=record.rows_failed,
                duration_ms=record.duration_ms,
                status=record.status,
                created_at=record.created_at,
            )
        )
    return result


@router.get("/history/{history_id}", response_model=TimesheetImportHistoryDetail)
def get_timesheet_import_history_detail(history_id: UUID, db: Session = Depends(get_db)):
    record = get_import_history(db, history_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import history not found.",
        )
    imported_by = db.get(User, record.imported_by_id)
    return TimesheetImportHistoryDetail(
        id=record.id,
        filename=record.filename,
        imported_by_name=(
            f"{imported_by.first_name} {imported_by.last_name}" if imported_by else "Unknown"
        ),
        designer_name=record.designer_name,
        date_range_label=record.date_range_label,
        rows_imported=record.rows_imported,
        rows_failed=record.rows_failed,
        duration_ms=record.duration_ms,
        status=record.status,
        created_at=record.created_at,
        log_json=record.log_json,
        upload_id=record.upload_id,
    )


@router.post("/history/{history_id}/re-import", response_model=TimesheetImportRunResponse)
def reimport_timesheet_history(
    history_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = get_import_history(db, history_id)
    if record is None or not record.upload_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import history not found or upload expired.",
        )
    try:
        analysis = analyze_upload(db, record.upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original upload file expired. Re-upload the file.",
        ) from exc

    context = load_resolutions(record.upload_id)
    job_id = timesheet_import_job_store.create_job(analysis.total_rows)
    background_tasks.add_task(
        _execute_timesheet_import_job,
        job_id,
        record.upload_id,
        dry_run=False,
        context=context,
        imported_by_id=current_user.id,
    )
    return TimesheetImportRunResponse(job_id=job_id)
