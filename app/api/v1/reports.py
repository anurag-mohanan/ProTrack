from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.permissions import can_view_deleted_projects, can_view_reports
from app.services.reporting.report_authorization import (
    assert_report_user_allowed,
    log_report_generation,
)
from app.services.reporting.report_scope import ReportScopeForbidden, resolve_report_scope
from app.crud.reports import (
    get_billable_utilization_report,
    get_billable_vs_non_billable_report,
    get_customer_summary_report,
    get_designer_productivity_report,
    get_execution_status_summary_report,
    get_milestone_completion_report,
    get_monthly_np_trends_report,
    get_non_productive_hours_report,
    get_np_hours_by_designer_report,
    get_productive_hours_report,
    get_project_delay_report,
    get_project_hours_report,
    get_project_classification_report,
    get_project_portfolio_report,
    get_project_stage_summary_report,
    get_reports_bundle,
    get_timesheet_approval_report,
    get_timesheet_export_report,
    get_top_np_activities_report,
)
from app.crud.team_reports import (
    get_customer_by_team_report,
    get_designer_by_team_report,
    get_hours_by_team_report,
    get_monthly_team_summary_report,
    get_projects_by_team_report,
    get_quoted_vs_actual_by_team_report,
    get_team_profitability_report,
    get_team_utilization_report,
)
from app.models.enums import ExecutionStatus, ProjectClassification, ProjectStage
from app.crud.dashboard import get_designer_workload
from app.models.models import Customer, Stream, Team, User
from app.schemas.dashboard import DesignerWorkload
from app.schemas.reports import (
    BillableUtilizationReportRow,
    BillableVsNonBillableReportRow,
    CustomerSummaryReportRow,
    DesignerProductivityReportRow,
    ExecutionStatusSummaryRow,
    MilestoneCompletionReportRow,
    MonthlyNpTrendReportRow,
    NonProductiveHoursReportRow,
    NpHoursByDesignerReportRow,
    ProductiveHoursReportRow,
    ProjectDelayReportRow,
    ProjectHoursReportRow,
    ProjectClassificationReport,
    ProjectPortfolioReportRow,
    ProjectStageSummaryRow,
    ReportsBundle,
    TimesheetApprovalReportRow,
    TimesheetExportReportRow,
    TopNpActivityReportRow,
    ProjectsByTeamReportRow,
    HoursByTeamReportRow,
    QuotedVsActualByTeamReportRow,
    TeamUtilizationReportRow,
    CustomerByTeamReportRow,
    DesignerByTeamReportRow,
    TeamProfitabilityReportRow,
    MonthlyTeamSummaryRow,
)
from app.schemas.reporting import (
    CustomerTimesheetPackPayload,
    DesignerTeamTimesheetPayload,
    EngineeringReportPayload,
    ReportCatalog,
    ReportScheduleEntry,
    ReportScheduleRequest,
)
from app.schemas.engineering_performance import EngineeringPerformanceReport
from app.schemas.quote_to_delivery import QuoteToDeliveryReport
from app.services.reporting.quote_to_delivery import (
    CLASSIFICATION_LABELS,
    POPULATION_LABELS,
    QtdFilters,
    QtdTableOptions,
    build_quote_to_delivery,
)
from app.services.reporting import reporting_engine
from app.services.reporting.customer_timesheet_pack import build_customer_timesheet_pack
from app.services.reporting.engineering_performance import (
    PerformanceFilters,
    build_engineering_performance,
)
from app.services.reporting.designer_team_timesheet import (
    build_designer_team_timesheet,
    is_designer_team_timesheet_report,
)
from app.services.reporting.excel.customer_timesheet import generate_customer_timesheet_excel
from app.services.reporting.excel.designer_team_timesheet import generate_designer_team_timesheet_excel
from app.services.reporting.export_filenames import (
    customer_timesheet_download_filename,
    engineering_report_download_filename,
    stream_scoped_download_filename,
    team_timesheet_download_filename,
)
from app.services.reporting.schedule_store import list_schedules, upsert_schedule
from app.services.reporting.timesheet_report_sections import (
    TIMESHEET_REPORT_SECTIONS,
    TIMESHEET_SECTION_DESCRIPTIONS,
    SECTION_ORDER,
    parse_timesheet_sections,
)

def _require_report_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_view_reports(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to Reports. Ask an administrator for the Reports module.",
        )
    return current_user


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(_require_report_access)],
)


def _report_options(
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    return {
        "include_archived": include_archived,
        "include_deleted": include_deleted,
    }


def _project_report_options(
    team_id: UUID | None = None,
    stream_id: UUID | None = None,
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    try:
        scope = resolve_report_scope(
            db,
            current_user,
            team_id=team_id,
            stream_id=stream_id,
        )
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from app.core.team_access import project_visibility_clause

    options: dict[str, object] = {
        "include_archived": include_archived,
        "include_deleted": include_deleted,
        "visibility_clause": project_visibility_clause(db, current_user),
        "stream_id": stream_id,
    }
    if scope.team_ids is not None:
        options["team_ids"] = scope.team_ids
    elif team_id is not None:
        options["team_ids"] = frozenset({team_id})
    return options


def _engineering_report_options(
    period_type: str = Query("monthly"),
    anchor: date | None = Query(None),
    customer_id: UUID | None = Query(None),
    team_id: UUID | None = Query(None),
    stream_id: UUID | None = Query(None),
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    sections: str | None = Query(
        None,
        description="Comma-separated timesheet report section ids (designers, projects, cross_team, utilization)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    try:
        scope = resolve_report_scope(
            db,
            current_user,
            customer_id=customer_id,
            team_id=team_id,
            stream_id=stream_id,
        )
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    selected_sections = parse_timesheet_sections(sections)
    return {
        "period_type": period_type,
        "anchor": anchor,
        "include_archived": include_archived,
        "include_deleted": include_deleted,
        "scope": scope,
        "sections": selected_sections,
    }


def _engine_kwargs(options: dict[str, object]) -> dict[str, object]:
    """Engineering reports take the shared filters but not the timesheet-only ``sections``."""
    return {key: value for key, value in options.items() if key != "sections"}


@router.get("/catalog", response_model=ReportCatalog)
def engineering_report_catalog():
    return reporting_engine.catalog()


@router.get("/timesheet-sections")
def timesheet_report_sections_catalog():
    """Selectable sections for designer/team timesheet Excel exports."""
    return [
        {
            "id": section_id,
            "label": TIMESHEET_REPORT_SECTIONS[section_id],
            "description": TIMESHEET_SECTION_DESCRIPTIONS.get(section_id, ""),
        }
        for section_id in SECTION_ORDER
    ]


@router.get(
    "/customer-timesheet-pack/preview",
    response_model=CustomerTimesheetPackPayload,
)
def customer_timesheet_pack_preview(
    customer_id: UUID = Query(...),
    period_type: str = Query("weekly"),
    anchor: date | None = Query(None),
    team_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return build_customer_timesheet_pack(
            db,
            customer_id=customer_id,
            current_user=current_user,
            period_type=period_type,
            anchor=anchor,
            team_id=team_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/customer-timesheet-pack/export.xlsx")
def customer_timesheet_pack_export(
    customer_id: UUID = Query(...),
    period_type: str = Query("weekly"),
    anchor: date | None = Query(None),
    team_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = build_customer_timesheet_pack(
            db,
            customer_id=customer_id,
            current_user=current_user,
            period_type=period_type,
            anchor=anchor,
            team_id=team_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    content = generate_customer_timesheet_excel(payload)
    filename = customer_timesheet_download_filename(
        customer_name=payload.customer_name,
        period_type=period_type,
        period_start=payload.period.start_date,
        week_number=payload.week_number,
    )
    log_report_generation(
        db,
        user=current_user,
        report_type="customer-timesheet-pack",
        filters={
            "customer_id": str(customer_id),
            "period_type": period_type,
            "anchor": anchor.isoformat() if anchor else None,
            "team_id": str(team_id) if team_id else None,
        },
        team_id=team_id,
        filename=filename,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/engine/{report_id}/preview",
    response_model=EngineeringReportPayload | DesignerTeamTimesheetPayload,
)
def engineering_report_preview(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    options: dict[str, object] = Depends(_engineering_report_options),
):
    if report_id == "customer-timesheet-pack":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /reports/customer-timesheet-pack/preview with customer_id",
        )
    if is_designer_team_timesheet_report(report_id):
        return build_designer_team_timesheet(
            db,
            current_user=current_user,
            report_id=report_id,
            period_type=str(options.get("period_type") or "monthly"),
            anchor=options.get("anchor"),  # type: ignore[arg-type]
            include_archived=bool(options.get("include_archived", True)),
            include_deleted=bool(options.get("include_deleted", False)),
            scope=options.get("scope"),  # type: ignore[arg-type]
            sections=options.get("sections"),  # type: ignore[arg-type]
        )
    try:
        return reporting_engine.build_report(db, report_id=report_id, **_engine_kwargs(options))
    except KeyError as exc:
        if "Unknown report" in str(exc) or "not registered" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.get("/engine/{report_id}/export.xlsx")
def engineering_report_export(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    options: dict[str, object] = Depends(_engineering_report_options),
):
    if report_id == "customer-timesheet-pack":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /reports/customer-timesheet-pack/export.xlsx with customer_id",
        )
    try:
        if is_designer_team_timesheet_report(report_id):
            scope = options.get("scope")
            customer_id = getattr(scope, "customer_id", None) if scope is not None else None
            timesheet_payload = build_designer_team_timesheet(
                db,
                current_user=current_user,
                report_id=report_id,
                period_type=str(options.get("period_type") or "monthly"),
                anchor=options.get("anchor"),  # type: ignore[arg-type]
                include_archived=bool(options.get("include_archived", True)),
                include_deleted=bool(options.get("include_deleted", False)),
                scope=scope,  # type: ignore[arg-type]
                sections=options.get("sections"),  # type: ignore[arg-type]
            )
            content = generate_designer_team_timesheet_excel(timesheet_payload)
            period_type = str(options.get("period_type") or timesheet_payload.period.period_type)
            week_number = (
                timesheet_payload.period.start_date.isocalendar()[1]
                if period_type == "weekly"
                else None
            )
            if customer_id is not None:
                customer = db.get(Customer, customer_id)
                customer_name = customer.name if customer else "Customer"
                filename = customer_timesheet_download_filename(
                    customer_name=customer_name,
                    period_type=period_type,
                    period_start=timesheet_payload.period.start_date,
                    week_number=week_number,
                )
            else:
                team_name = "All_Teams"
                scoped_team_id = getattr(scope, "team_id", None) if scope is not None else None
                if scoped_team_id is None and scope is not None:
                    team_ids = getattr(scope, "team_ids", None)
                    if team_ids is not None and len(team_ids) == 1:
                        scoped_team_id = next(iter(team_ids))
                if scoped_team_id is not None:
                    team = db.get(Team, scoped_team_id)
                    if team is not None:
                        team_name = team.name
                elif timesheet_payload.team_count == 1 and timesheet_payload.designers:
                    team_name = timesheet_payload.designers[0].team_name or "All_Teams"
                scoped_stream_id = getattr(scope, "stream_id", None) if scope is not None else None
                if scoped_stream_id is not None:
                    stream = db.get(Stream, scoped_stream_id)
                    stream_name = stream.name if stream is not None else "Stream"
                    filename = stream_scoped_download_filename(
                        stream_name=stream_name,
                        subject=team_name,
                        period_type=period_type,
                        period_start=timesheet_payload.period.start_date,
                        week_number=week_number,
                    )
                else:
                    filename = team_timesheet_download_filename(
                        team_name=team_name,
                        period_type=period_type,
                        period_start=timesheet_payload.period.start_date,
                        week_number=week_number,
                    )
        else:
            payload = reporting_engine.build_report(db, report_id=report_id, **_engine_kwargs(options))
            content = reporting_engine.export_excel(payload)
            period_type = str(options.get("period_type") or payload.period.period_type)
            week_number = (
                payload.period.start_date.isocalendar()[1]
                if period_type == "weekly"
                else None
            )
            scope = options.get("scope")
            subject = None
            scoped_team_id = getattr(scope, "team_id", None) if scope is not None else None
            if scoped_team_id is None and scope is not None:
                team_ids = getattr(scope, "team_ids", None)
                if team_ids is not None and len(team_ids) == 1:
                    scoped_team_id = next(iter(team_ids))
            if scoped_team_id is not None:
                team = db.get(Team, scoped_team_id)
                if team is not None:
                    subject = team.name
            scoped_stream_id = getattr(scope, "stream_id", None) if scope is not None else None
            if scoped_stream_id is not None:
                stream = db.get(Stream, scoped_stream_id)
                stream_name = stream.name if stream is not None else "Stream"
                filename = stream_scoped_download_filename(
                    stream_name=stream_name,
                    subject=subject,
                    period_type=period_type,
                    period_start=payload.period.start_date,
                    week_number=week_number,
                )
            else:
                filename = engineering_report_download_filename(
                    report_id=report_id,
                    period_type=period_type,
                    period_start=payload.period.start_date,
                    subject=subject,
                    week_number=week_number,
                )
    except KeyError as exc:
        if "Unknown report" in str(exc) or "not registered" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise

    scope = options.get("scope")
    scoped_team_id = None
    if scope is not None:
        team_ids = getattr(scope, "team_ids", None)
        if team_ids is not None and len(team_ids) == 1:
            scoped_team_id = next(iter(team_ids))
    anchor = options.get("anchor")
    log_report_generation(
        db,
        user=current_user,
        report_type=report_id,
        filters={
            "period_type": str(options.get("period_type") or ""),
            "anchor": anchor.isoformat() if hasattr(anchor, "isoformat") else anchor,
            "customer_id": str(getattr(scope, "customer_id", None))
            if scope is not None and getattr(scope, "customer_id", None)
            else None,
            "team_id": str(scoped_team_id) if scoped_team_id else None,
            "stream_id": str(getattr(scope, "stream_id", None))
            if scope is not None and getattr(scope, "stream_id", None)
            else None,
        },
        team_id=scoped_team_id,
        filename=filename,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_PERFORMANCE_PERIODS = {"weekly", "monthly", "quarterly", "yearly", "custom"}


def _performance_filters(
    period_type: str = Query("monthly"),
    anchor: date | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    plan_basis: str = Query("current"),
    customer_id: UUID | None = Query(None),
    end_customer_id: UUID | None = Query(None),
    team_id: UUID | None = Query(None),
    design_leader_id: UUID | None = Query(None),
    designer_id: UUID | None = Query(None),
    surfacer_id: UUID | None = Query(None),
    project_type_id: UUID | None = Query(None),
    template_id: UUID | None = Query(None),
    include_archived: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> tuple[PerformanceFilters, dict[str, str | None]]:
    from app.core.team_access import project_visibility_clause
    from app.models.models import ProjectTemplate, ProjectType

    if period_type not in _PERFORMANCE_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"period_type must be one of: {', '.join(sorted(_PERFORMANCE_PERIODS))}",
        )
    if plan_basis not in {"current", "original"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="plan_basis must be 'current' or 'original'",
        )
    try:
        scope = resolve_report_scope(db, current_user, customer_id=customer_id, team_id=team_id)
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    template_family_id = None
    if template_id is not None:
        template = db.get(ProjectTemplate, template_id)
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        template_family_id = template.template_family_id or template.id

    def _label(model, ref):
        if ref is None:
            return None
        row = db.get(model, ref)
        if row is None:
            return str(ref)
        if isinstance(row, User):
            return f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email
        return getattr(row, "name", str(ref))

    filters = PerformanceFilters(
        period_type=period_type,
        anchor=anchor,
        start_date=start_date,
        end_date=end_date,
        plan_basis=plan_basis,
        customer_id=customer_id,
        end_customer_id=end_customer_id,
        team_ids=scope.team_ids if scope.team_ids is not None else (
            frozenset({team_id}) if team_id is not None else None
        ),
        design_leader_id=design_leader_id,
        designer_id=designer_id,
        surfacer_id=surfacer_id,
        project_type_id=project_type_id,
        template_family_id=template_family_id,
        include_archived=include_archived,
        visibility_clause=project_visibility_clause(db, current_user),
    )
    labels = {
        "customer": _label(Customer, customer_id),
        "end_customer": _label(Customer, end_customer_id),
        "team": _label(Team, team_id),
        "design_leader": _label(User, design_leader_id),
        "designer": _label(User, designer_id),
        "surfacer": _label(User, surfacer_id),
        "project_type": _label(ProjectType, project_type_id),
        "template": _label(ProjectTemplate, template_id),
        "plan_basis": "Original estimate" if plan_basis == "original" else "Current approved estimate",
    }
    return filters, labels


def _build_performance(db: Session, params) -> EngineeringPerformanceReport:
    filters, labels = params
    try:
        return build_engineering_performance(db, filters, filter_labels=labels)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/engineering-data-quality")
def engineering_data_quality(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records that make schedules and KPIs unreliable, within the viewer's project scope."""
    from app.core.team_access import project_visibility_clause
    from app.services.reporting.engineering_data_quality import build_engineering_data_quality

    return build_engineering_data_quality(
        db, visibility_clause=project_visibility_clause(db, current_user)
    )


@router.get("/engineering-performance", response_model=EngineeringPerformanceReport)
def engineering_performance_report(
    db: Session = Depends(get_db),
    params=Depends(_performance_filters),
):
    return _build_performance(db, params)


@router.get("/engineering-performance/export.xlsx")
def engineering_performance_export(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    params=Depends(_performance_filters),
):
    from app.core.access_control import SPECIAL_EXPORT_REPORTS
    from app.core.permissions import user_holds_special
    from app.models.foundation import CompanySettings
    from app.services.reporting.excel.engineering_performance import (
        generate_engineering_performance_excel,
    )

    if not user_holds_special(db, current_user, SPECIAL_EXPORT_REPORTS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires the 'export_reports' permission.",
        )
    report = _build_performance(db, params)
    settings = db.scalar(select(CompanySettings).limit(1))
    company_name = (settings.company_name if settings and settings.company_name else "ProTrack")
    content = generate_engineering_performance_excel(report, company_name=company_name)
    filename = (
        f"Engineering_Performance_{report.period.period_type}_"
        f"{report.period.start_date:%Y%m%d}-{report.period.end_date:%Y%m%d}.xlsx"
    )
    filters, _labels = params
    log_report_generation(
        db,
        user=current_user,
        report_type="engineering-performance",
        filters={
            "period_type": report.period.period_type,
            "start_date": report.period.start_date.isoformat(),
            "end_date": report.period.end_date.isoformat(),
            "customer_id": str(filters.customer_id) if filters.customer_id else None,
            "plan_basis": filters.plan_basis,
        },
        team_id=next(iter(filters.team_ids)) if filters.team_ids and len(filters.team_ids) == 1 else None,
        filename=filename,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _qtd_params(
    params=Depends(_performance_filters),
    population: str = Query("completed"),
    project_classification: ProjectClassification | None = Query(None),
    status_filter: ExecutionStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=100),
    segment: str | None = Query(None),
    stage: str | None = Query(None),
    sort: str | None = Query(None),
) -> tuple[QtdFilters, QtdTableOptions, dict[str, str | None]]:
    base, labels = params
    labels = {key: value for key, value in labels.items() if key != "plan_basis"}
    labels["population"] = POPULATION_LABELS.get(population, (population,))[0]
    labels["classification"] = (
        CLASSIFICATION_LABELS.get(project_classification.value) if project_classification else None
    )
    labels["status"] = status_filter.value.replace("_", " ").capitalize() if status_filter else None
    filters = QtdFilters(
        base=base,
        population=population,
        classification=project_classification,
        status=status_filter,
    )
    options = QtdTableOptions(search=search, segment=segment, stage=stage, sort=sort)
    return filters, options, labels


def _build_qtd(db: Session, filters: QtdFilters, options: QtdTableOptions, labels) -> QuoteToDeliveryReport:
    try:
        return build_quote_to_delivery(db, filters, options, filter_labels=labels)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/quote-to-delivery", response_model=QuoteToDeliveryReport)
def quote_to_delivery_report(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    params=Depends(_qtd_params),
):
    """Quote-to-Delivery report; the project table is paginated, aggregates cover all rows."""
    filters, options, labels = params
    options.page = page
    options.page_size = page_size
    return _build_qtd(db, filters, options, labels)


@router.get("/quote-to-delivery/export.xlsx")
def quote_to_delivery_export(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    params=Depends(_qtd_params),
):
    """Every row matching the filters, search and segment — not only the visible page."""
    from app.core.access_control import SPECIAL_EXPORT_REPORTS
    from app.core.permissions import user_holds_special
    from app.models.foundation import CompanySettings
    from app.services.reporting.excel.quote_to_delivery import (
        generate_quote_to_delivery_excel,
    )

    if not user_holds_special(db, current_user, SPECIAL_EXPORT_REPORTS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires the 'export_reports' permission.",
        )
    filters, options, labels = params
    options.page_size = None
    report = _build_qtd(db, filters, options, labels)
    settings = db.scalar(select(CompanySettings).limit(1))
    company_name = settings.company_name if settings and settings.company_name else "ProTrack"
    try:
        content = generate_quote_to_delivery_excel(report, company_name=company_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if filters.population == "completed":
        span = f"{report.period.start_date:%Y%m%d}-{report.period.end_date:%Y%m%d}"
    else:
        span = f"open_{report.population.as_of:%Y%m%d}"
    filename = f"Quote_to_Delivery_{span}.xlsx"
    base = filters.base
    log_report_generation(
        db,
        user=current_user,
        report_type="quote-to-delivery",
        filters={
            "population": filters.population,
            "period_type": report.period.period_type,
            "start_date": report.period.start_date.isoformat(),
            "end_date": report.period.end_date.isoformat(),
            "customer_id": str(base.customer_id) if base.customer_id else None,
            "classification": filters.classification.value if filters.classification else None,
            "status": filters.status.value if filters.status else None,
            "search": options.search,
            "segment": options.segment,
            "stage": options.stage,
            "rows": report.projects.total,
        },
        team_id=next(iter(base.team_ids)) if base.team_ids and len(base.team_ids) == 1 else None,
        filename=filename,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/schedules", response_model=list[ReportScheduleEntry])
def engineering_report_schedules():
    return list_schedules()


@router.put("/schedules", response_model=ReportScheduleEntry)
def save_engineering_report_schedule(payload: ReportScheduleRequest):
    return upsert_schedule(payload)


@router.get("", response_model=ReportsBundle)
def list_reports(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_reports_bundle(db, **options)


@router.get("/project-hours", response_model=list[ProjectHoursReportRow])
def project_hours_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_project_report_options),
):
    return get_project_hours_report(db, **options)


@router.get("/project-classification", response_model=ProjectClassificationReport)
def project_classification_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_project_report_options),
):
    return get_project_classification_report(db, **options)


@router.get("/designer-utilization", response_model=list[DesignerWorkload])
def designer_utilization_report(db: Session = Depends(get_db)):
    return get_designer_workload(db)


@router.get("/customer-summary", response_model=list[CustomerSummaryReportRow])
def customer_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_customer_summary_report(db, **options)


@router.get("/timesheet-approval", response_model=list[TimesheetApprovalReportRow])
def timesheet_approval_report(db: Session = Depends(get_db)):
    return get_timesheet_approval_report(db)


@router.get("/project-delay", response_model=list[ProjectDelayReportRow])
def project_delay_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_delay_report(db, **options)


@router.get("/milestone-completion", response_model=list[MilestoneCompletionReportRow])
def milestone_completion_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_milestone_completion_report(db, **options)


@router.get("/designer-productivity", response_model=list[DesignerProductivityReportRow])
def designer_productivity_report(db: Session = Depends(get_db)):
    return get_designer_productivity_report(db)


@router.get("/productive-hours", response_model=list[ProductiveHoursReportRow])
def productive_hours_report(db: Session = Depends(get_db)):
    return get_productive_hours_report(db)


@router.get("/non-productive-hours", response_model=list[NonProductiveHoursReportRow])
def non_productive_hours_report(db: Session = Depends(get_db)):
    return get_non_productive_hours_report(db)


@router.get("/billable-utilization", response_model=list[BillableUtilizationReportRow])
def billable_utilization_report(db: Session = Depends(get_db)):
    return get_billable_utilization_report(db)


@router.get("/monthly-np-trends", response_model=list[MonthlyNpTrendReportRow])
def monthly_np_trends_report(db: Session = Depends(get_db)):
    return get_monthly_np_trends_report(db)


@router.get("/np-hours-by-designer", response_model=list[NpHoursByDesignerReportRow])
def np_hours_by_designer_report(db: Session = Depends(get_db)):
    return get_np_hours_by_designer_report(db)


@router.get("/billable-vs-non-billable", response_model=BillableVsNonBillableReportRow)
def billable_vs_non_billable_report(db: Session = Depends(get_db)):
    return get_billable_vs_non_billable_report(db)


@router.get("/top-np-activities", response_model=list[TopNpActivityReportRow])
def top_np_activities_report(db: Session = Depends(get_db)):
    return get_top_np_activities_report(db)


@router.get("/timesheet-export", response_model=list[TimesheetExportReportRow])
def timesheet_export_report(
    period: str = Query("monthly", pattern="^(daily|weekly|monthly|quarterly|yearly)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    user_id: UUID | None = None,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
    project_id: UUID | None = None,
    task_type_id: UUID | None = None,
    billable: str | None = Query(None, pattern="^(billable|non_billable)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        scope = resolve_report_scope(
            db,
            current_user,
            customer_id=customer_id,
            team_id=team_id,
            range_start=date_from,
            range_end=date_to,
        )
        assert_report_user_allowed(db, current_user, user_id, roster=scope.user_ids)
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    rows = get_timesheet_export_report(
        db,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        user_ids=None if user_id is not None else scope.user_ids,
        team_id=team_id,
        customer_id=customer_id,
        project_id=project_id,
        task_type_id=task_type_id,
        billable=billable,
    )

    log_report_generation(
        db,
        user=current_user,
        report_type="timesheet-export",
        filters={
            "period": period,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "user_id": str(user_id) if user_id else None,
            "team_id": str(team_id) if team_id else None,
            "customer_id": str(customer_id) if customer_id else None,
            "project_id": str(project_id) if project_id else None,
            "task_type_id": str(task_type_id) if task_type_id else None,
            "billable": billable,
        },
        team_id=team_id,
    )
    return rows


@router.get("/project-portfolio", response_model=list[ProjectPortfolioReportRow])
def project_portfolio_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_project_report_options),
):
    return get_project_portfolio_report(db, **options)


@router.get("/project-stage-summary", response_model=list[ProjectStageSummaryRow])
def project_stage_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_project_stage_summary_report(db, **options)


@router.get("/execution-status-summary", response_model=list[ExecutionStatusSummaryRow])
def execution_status_summary_report(
    db: Session = Depends(get_db),
    options: dict[str, bool] = Depends(_report_options),
):
    return get_execution_status_summary_report(db, **options)


def _team_report_options(
    team_id: UUID | None = None,
    include_archived: bool = Query(True),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    from app.core.team_access import resolve_team_scope

    if include_deleted and not can_view_deleted_projects(db, current_user):
        include_deleted = False
    scoped = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped is not None and team_id is not None and team_id not in scoped:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    options: dict[str, object] = {
        "team_id": team_id,
        "include_archived": include_archived,
        "include_deleted": include_deleted,
    }
    if scoped is not None and team_id is None:
        options["_scope_team_ids"] = scoped
    return options


def _run_team_report(getter, db: Session, options: dict[str, object]):
    scope = options.pop("_scope_team_ids", None)
    rows = getter(db, **options)
    if scope is None:
        return rows
    return [row for row in rows if getattr(row, "team_id", None) in scope]


@router.get("/projects-by-team", response_model=list[ProjectsByTeamReportRow])
def projects_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return _run_team_report(get_projects_by_team_report, db, options)


@router.get("/hours-by-team", response_model=list[HoursByTeamReportRow])
def hours_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return _run_team_report(get_hours_by_team_report, db, options)


@router.get("/quoted-vs-actual-by-team", response_model=list[QuotedVsActualByTeamReportRow])
def quoted_vs_actual_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return _run_team_report(get_quoted_vs_actual_by_team_report, db, options)


@router.get("/team-utilization", response_model=list[TeamUtilizationReportRow])
def team_utilization_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.core.team_access import resolve_team_scope

    scoped = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped is not None and team_id is not None and team_id not in scoped:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    rows = get_team_utilization_report(db, team_id=team_id)
    if scoped is None:
        return rows
    return [row for row in rows if row.team_id in scoped]


@router.get("/customer-by-team", response_model=list[CustomerByTeamReportRow])
def customer_by_team_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return _run_team_report(get_customer_by_team_report, db, options)


@router.get("/designer-by-team", response_model=list[DesignerByTeamReportRow])
def designer_by_team_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.core.team_access import resolve_team_scope

    scoped = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped is not None and team_id is not None and team_id not in scoped:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    rows = get_designer_by_team_report(db, team_id=team_id)
    if scoped is None:
        return rows
    return [row for row in rows if row.team_id in scoped]


@router.get("/team-profitability", response_model=list[TeamProfitabilityReportRow])
def team_profitability_report(
    db: Session = Depends(get_db),
    options: dict[str, object] = Depends(_team_report_options),
):
    return _run_team_report(get_team_profitability_report, db, options)


@router.get("/monthly-team-summary", response_model=list[MonthlyTeamSummaryRow])
def monthly_team_summary_report(
    db: Session = Depends(get_db),
    team_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.core.team_access import resolve_team_scope

    scoped = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped is not None and team_id is not None and team_id not in scoped:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team is outside your accessible scope",
        )
    rows = get_monthly_team_summary_report(db, team_id=team_id)
    if scoped is None:
        return rows
    return [row for row in rows if row.team_id in scoped]
