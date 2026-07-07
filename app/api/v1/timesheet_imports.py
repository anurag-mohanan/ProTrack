from datetime import datetime
import logging
from pathlib import Path
import shutil
from tempfile import gettempdir
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, Response
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
from app.schemas.historical_timesheet_folder_import import (
    FolderBatchUploadResponse,
    FolderImportRunRequest,
    FolderImportRunResponse,
    FolderImportJobProgress,
    FolderScanRequest,
    FolderScanResponse,
    TimesheetResetRequest,
    TimesheetResetResponse,
)
from app.services.historical_timesheet_folder_import_service import (
    create_pre_import_backup,
    import_log_to_excel,
    run_folder_import,
    save_folder_batch,
    scan_folder_source,
)
from app.services.timesheet_folder_import_job_store import timesheet_folder_import_job_store
from app.services.timesheet_import_job_store import timesheet_import_job_store
from app.schemas.historical_timesheet_master_import import (
    MasterImportJobProgress,
    MasterImportRunRequest,
    MasterImportRunResponse,
    MasterScanResponse,
    MasterUploadResponse,
)
from app.services.historical_timesheet_master_import_service import (
    get_master_upload,
    master_import_log_to_excel,
    run_master_import,
    save_master_upload,
    scan_master_workbook,
)
from app.services.timesheet_master_import_job_store import timesheet_master_import_job_store
from app.services.timesheet_reset_service import delete_all_timesheet_data

router = APIRouter(
    prefix="/imports/historical-timesheets",
    tags=["imports"],
    dependencies=[Depends(require_roles("Admin"))],
)
logger = logging.getLogger(__name__)


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
        ignore_duplicate_check=payload.ignore_duplicate_check,
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


@router.post("/folder/upload", response_model=FolderBatchUploadResponse)
async def upload_historical_timesheet_folder(
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(...),
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one Excel file is required.",
        )
    if len(files) != len(paths):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Each uploaded file must include a relative path.",
        )

    payload: list[tuple[str, bytes]] = []
    for upload, rel_path in zip(files, paths, strict=True):
        if not upload.filename:
            continue
        name = upload.filename
        if name.startswith("~$") or not name.lower().endswith(".xlsx"):
            continue
        content = await upload.read()
        if not content:
            continue
        payload.append((rel_path, content))

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid .xlsx files were provided.",
        )

    batch_id = str(uuid4())
    save_folder_batch(batch_id, payload)
    root_name = paths[0].split("/")[0].split("\\")[0] if paths else "Uploaded folder"
    return FolderBatchUploadResponse(
        batch_id=batch_id,
        file_count=len(payload),
        source_label=root_name,
    )


@router.post("/folder/scan", response_model=FolderScanResponse)
def scan_historical_timesheet_folder(payload: FolderScanRequest):
    if not payload.batch_id and not payload.source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either batch_id or source_path is required.",
        )
    try:
        return scan_folder_source(
            batch_id=payload.batch_id,
            source_path=payload.source_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _execute_folder_import_job(
    job_id: str,
    *,
    batch_id: str | None,
    source_path: str | None,
    imported_by_id: UUID,
    backup_path,
    after_database_reset: bool = False,
    ignore_duplicate_check: bool = True,
) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        timesheet_folder_import_job_store.mark_running(job_id)

        def progress_callback(**kwargs) -> None:
            timesheet_folder_import_job_store.update_progress(job_id, **kwargs)

        summary, log_rows = run_folder_import(
            db,
            batch_id=batch_id,
            source_path=source_path,
            imported_by_id=imported_by_id,
            progress_callback=progress_callback,
            cancel_check=lambda: timesheet_folder_import_job_store.is_cancelled(job_id),
            backup_path=backup_path,
            after_database_reset=after_database_reset,
            ignore_duplicate_check=ignore_duplicate_check,
        )
        cancelled = timesheet_folder_import_job_store.is_cancelled(job_id)
        log_name = f"HistoricalImportLog_{datetime.now().strftime('%Y%m%d')}.xlsx"
        timesheet_folder_import_job_store.complete(
            job_id,
            summary=summary,
            log_rows=log_rows,
            log_download_name=log_name,
            cancelled=cancelled,
        )
    except Exception as exc:
        timesheet_folder_import_job_store.fail(job_id, str(exc))
    finally:
        db.close()


@router.post("/folder/run", response_model=FolderImportRunResponse)
def run_historical_timesheet_folder_import(
    payload: FolderImportRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if not payload.batch_id and not payload.source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either batch_id or source_path is required.",
        )
    try:
        scan = scan_folder_source(
            batch_id=payload.batch_id,
            source_path=payload.source_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    backup_path = create_pre_import_backup()
    job_id = timesheet_folder_import_job_store.create_job(
        files_total=scan.file_count,
        rows_total=scan.estimated_entries,
    )
    background_tasks.add_task(
        _execute_folder_import_job,
        job_id,
        batch_id=payload.batch_id,
        source_path=payload.source_path,
        imported_by_id=current_user.id,
        backup_path=backup_path,
        after_database_reset=payload.after_database_reset,
        ignore_duplicate_check=payload.ignore_duplicate_check,
    )
    return FolderImportRunResponse(
        job_id=job_id,
        backup_path=str(backup_path) if backup_path else None,
    )


@router.get("/folder/jobs/{job_id}", response_model=FolderImportJobProgress)
def get_folder_import_job(job_id: str):
    job = timesheet_folder_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder import job not found.",
        )
    return job


@router.post("/folder/jobs/{job_id}/cancel")
def cancel_folder_import_job(job_id: str):
    if not timesheet_folder_import_job_store.request_cancel(job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder import job not found.",
        )
    return {"status": "cancel_requested"}


@router.get("/folder/jobs/{job_id}/log.xlsx")
def download_folder_import_log(job_id: str):
    job = timesheet_folder_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder import job not found.",
        )
    content = import_log_to_excel(job.log_rows)
    filename = job.log_download_name or "HistoricalImportLog.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _execute_master_import_job(
    job_id: str,
    *,
    upload_id: str,
    workbook_path: str,
    selected_designers: list[str] | None,
    backup_path,
) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        logger.info(
            "Master import background task started job_id=%s upload_id=%s workbook_path=%s",
            job_id,
            upload_id,
            workbook_path,
        )
        timesheet_master_import_job_store.mark_running(
            job_id, message="Opening workbook..."
        )
        timesheet_master_import_job_store.update_progress(
            job_id,
            percent_complete=1,
            rows_processed=0,
            rows_imported=0,
            message="Opening workbook...",
        )

        def progress_callback(**kwargs) -> None:
            timesheet_master_import_job_store.update_progress(job_id, **kwargs)

        designer_filter = set(selected_designers) if selected_designers else None
        summary, log_rows = run_master_import(
            db,
            upload_id=upload_id,
            workbook_path_override=workbook_path,
            selected_designers=designer_filter,
            progress_callback=progress_callback,
            cancel_check=lambda: timesheet_master_import_job_store.is_cancelled(job_id),
            backup_path=backup_path,
        )
        cancelled = timesheet_master_import_job_store.is_cancelled(job_id)
        log_name = f"MasterHistoricalImportLog_{datetime.now().strftime('%Y%m%d')}.xlsx"
        timesheet_master_import_job_store.complete(
            job_id,
            summary=summary,
            log_rows=log_rows,
            log_download_name=log_name,
            cancelled=cancelled,
        )
    except Exception as exc:
        logger.exception("Master import job failed job_id=%s", job_id)
        timesheet_master_import_job_store.fail(job_id, f"Import failed: {exc}")
    finally:
        db.close()


@router.post("/master/upload", response_model=MasterUploadResponse)
async def upload_master_timesheet_workbook(
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
        save_master_upload(upload_id, file.filename, content)
        scan = scan_master_workbook(db, upload_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return MasterUploadResponse(upload_id=upload_id, filename=file.filename, scan=scan)


@router.get("/master/upload/{upload_id}/scan", response_model=MasterScanResponse)
def rescan_master_timesheet_workbook(upload_id: str, db: Session = Depends(get_db)):
    try:
        return scan_master_workbook(db, upload_id)
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


@router.post("/master/run", response_model=MasterImportRunResponse)
def run_master_timesheet_import(
    payload: MasterImportRunRequest,
    background_tasks: BackgroundTasks,
):
    logger.info("Import request received upload_id=%s", payload.upload_id)
    try:
        upload_workbook_path, _ = get_master_upload(payload.upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or expired.",
        ) from exc

    if not upload_workbook_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded workbook file was not found.",
        )

    backup_path = create_pre_import_backup()
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        scan = scan_master_workbook(db, payload.upload_id)
    finally:
        db.close()

    job_id = timesheet_master_import_job_store.create_job(rows_total=scan.row_count)
    worker_dir = Path(gettempdir()) / "protrack_master_timesheet_import_worker"
    worker_dir.mkdir(parents=True, exist_ok=True)
    worker_path = worker_dir / f"{job_id}.xlsx"
    try:
        shutil.copy2(upload_workbook_path, worker_path)
    except Exception as exc:
        logger.exception(
            "Failed to copy workbook for background worker upload_id=%s path=%s",
            payload.upload_id,
            upload_workbook_path,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare workbook for import: {exc}",
        ) from exc
    logger.info("Workbook copied to worker path job_id=%s path=%s", job_id, worker_path)

    logger.info("Background job created job_id=%s rows_total=%s", job_id, scan.row_count)
    background_tasks.add_task(
        _execute_master_import_job,
        job_id,
        upload_id=payload.upload_id,
        workbook_path=str(worker_path),
        selected_designers=payload.designers,
        backup_path=backup_path,
    )
    return MasterImportRunResponse(
        job_id=job_id,
        backup_path=str(backup_path) if backup_path else None,
    )


@router.get("/master/jobs/{job_id}", response_model=MasterImportJobProgress)
def get_master_import_job(job_id: str):
    job = timesheet_master_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master import job not found.",
        )
    return job


@router.post("/master/jobs/{job_id}/cancel")
def cancel_master_import_job(job_id: str):
    if not timesheet_master_import_job_store.request_cancel(job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master import job not found.",
        )
    return {"status": "cancel_requested"}


@router.get("/master/jobs/{job_id}/log.xlsx")
def download_master_import_log(job_id: str):
    job = timesheet_master_import_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master import job not found.",
        )
    content = master_import_log_to_excel(job.log_rows)
    filename = job.log_download_name or "MasterHistoricalImportLog.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reset", response_model=TimesheetResetResponse)
def reset_all_timesheet_data(
    payload: TimesheetResetRequest,
    db: Session = Depends(get_db),
):
    if payload.confirmation.strip() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Type DELETE to confirm this operation.',
        )
    try:
        result = delete_all_timesheet_data(db)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return TimesheetResetResponse(
        backup_path=str(result.backup_path),
        timesheets_deleted=result.timesheets_deleted,
        entries_deleted=result.entries_deleted,
        import_history_deleted=result.import_history_deleted,
        deletion_logs_deleted=result.deletion_logs_deleted,
    )
