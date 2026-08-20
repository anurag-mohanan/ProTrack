from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.request_logging import RequestLoggingMiddleware
from fastapi.openapi.utils import get_openapi

import app.models  # noqa: F401 — register all models with Base.metadata
import app.models.finance  # noqa: F401 — register finance models
from app.api.v1.api import api_router
from app.api.public_v1 import router as public_api_router
from app.core.config import APP_VERSION, CORS_ORIGINS, ENABLE_DEMO_SEED, INTERNAL_RELEASE, RELEASE_CANDIDATE, UPLOAD_DIR
from app.core.openapi import fix_ref_siblings
from app.db.base import Base
from app.db.project_template_seed import (
    ensure_project_types_and_templates,
    validate_project_template_health,
)
from app.db.engineering_stream_seed import ensure_engineering_streams
from app.db.phase7_schema_sync import ensure_phase7_foundation
from app.db.phase8_schema_sync import ensure_phase8_foundation
from app.db.phase9_schema_sync import ensure_phase9_foundation
from app.db.phase10_milestone_schema_sync import ensure_phase10_milestone_foundation
from app.db.phase11_email_schema_sync import ensure_email_foundation
from app.db.phase12_email_communication_schema_sync import ensure_email_communication_foundation
from app.db.phase13_multi_team_schema_sync import ensure_phase13_multi_team_foundation
from app.db.phase14_kpi_schema_sync import ensure_phase14_kpi_foundation
from app.db.phase15_working_model_schema_sync import ensure_phase15_working_model_foundation
from app.db.phase16_timesheet_contribution_schema_sync import ensure_phase16_timesheet_contribution_foundation
from app.db.phase17_ebmp_finance_schema_sync import ensure_phase17_ebmp_finance_foundation
from app.db.phase18_finance_annual_plan_schema_sync import (
    ensure_phase18_finance_annual_plan_foundation,
)
from app.db.phase19_timesheet_report_inclusion_schema_sync import (
    ensure_phase19_timesheet_report_inclusion_foundation,
)
from app.db.phase20_project_complexity_schema_sync import ensure_project_complexity
from app.db.phase21_project_workorder_schema_sync import ensure_project_workorder_metadata
from app.db.phase22_finance_rebuild_schema_sync import ensure_phase22_finance_rebuild_foundation
from app.db.phase23_finance_team_scope_schema_sync import (
    ensure_phase23_finance_team_scope_foundation,
)
from app.db.phase24_user_requires_salary_schema_sync import (
    ensure_phase24_user_requires_salary_foundation,
)
from app.db.phase25_expense_purchase_date_schema_sync import (
    ensure_phase25_expense_purchase_date_foundation,
)
from app.db.phase26_customer_currency_schema_sync import (
    ensure_phase26_customer_currency_foundation,
)
from app.db.phase27_fx_rate_backfill import ensure_phase27_fx_rate_backfill
from app.db.phase28_team_member_billable_schema_sync import (
    ensure_phase28_team_member_billable_foundation,
)
from app.db.phase29_quote_team_schema_sync import ensure_phase29_quote_team_foundation
from app.db.phase30_quote_external_number_schema_sync import (
    ensure_phase30_quote_external_number_foundation,
)
from app.db.phase31_overhead_role_billable_backfill import (
    ensure_phase31_overhead_role_billable_backfill,
)
from app.db.phase32_finance_quarterly_fee_bands_schema_sync import (
    ensure_phase32_finance_quarterly_fee_bands_foundation,
)
from app.db.phase33_management_team_schema_sync import (
    ensure_phase33_management_team_foundation,
)
from app.db.phase34_quote_quoted_date_schema_sync import (
    ensure_phase34_quote_quoted_date_foundation,
)
from app.db.phase35_overhead_team_merge_schema_sync import (
    ensure_phase35_overhead_team_merge_foundation,
)
from app.db.phase36_team_membership_periods_schema_sync import (
    ensure_phase36_team_membership_periods_foundation,
)
from app.db.phase37_performance_reviews_schema_sync import (
    ensure_phase37_performance_reviews_foundation,
)
from app.db.phase38_performance_review_enhancements_schema_sync import (
    ensure_phase38_performance_review_enhancements,
)
from app.db.phase39_performance_review_projects_schema_sync import (
    ensure_phase39_performance_review_projects_foundation,
)
from app.db.phase40_performance_review_form_schema_sync import (
    ensure_phase40_performance_review_form_foundation,
)
from app.db.phase41_performance_review_experience_schema_sync import (
    ensure_phase41_performance_review_experience_foundation,
)
from app.db.phase42_performance_skill_matrix_schema_sync import (
    ensure_phase42_performance_skill_matrix_foundation,
)
from app.db.phase43_quote_invoiced_date_schema_sync import (
    ensure_phase43_quote_invoiced_date_foundation,
)
from app.db.phase44_quote_invoicing_schema_sync import (
    ensure_phase44_quote_invoicing_foundation,
)
from app.db.phase45_performance_review_engine_schema_sync import (
    ensure_phase45_performance_review_engine_foundation,
)
from app.db.phase46_org_department_schema_sync import (
    ensure_phase46_org_department_foundation,
)
from app.db.phase47_user_lifecycle_schema_sync import (
    ensure_phase47_user_lifecycle_foundation,
)
from app.db.phase48_compensation_change_schema_sync import (
    ensure_phase48_compensation_change_foundation,
)
from app.db.phase49_role_hierarchy_schema_sync import (
    ensure_phase49_role_hierarchy_foundation,
)
from app.db.phase50_security_foundation_schema_sync import (
    ensure_phase50_security_foundation,
)
from app.db.phase51_department_standardization_schema_sync import (
    ensure_phase51_department_standardization,
)
from app.db.phase52_ticketing_schema_sync import (
    ensure_phase52_ticketing_foundation,
)
from app.db.phase53_ticket_routing_schema_sync import (
    ensure_phase53_ticket_routing_foundation,
)
from app.db.phase54_onboarding_schema_sync import (
    ensure_phase54_onboarding_foundation,
)
from app.db.phase55_exit_process_schema_sync import (
    ensure_phase55_exit_process_foundation,
)
from app.db.phase56_hr_process_control_schema_sync import (
    ensure_phase56_hr_process_control_foundation,
)
from app.db.phase57_background_jobs_schema_sync import (
    ensure_phase57_background_jobs_foundation,
)
from app.db.phase58_r3_portfolio_schema_sync import (
    ensure_phase58_r3_portfolio_foundation,
)
from app.db.phase59_r4_enterprise_schema_sync import (
    ensure_phase59_r4_enterprise_foundation,
)
from app.db.phase60_quote_payment_schema_sync import (
    ensure_phase60_quote_payment_foundation,
)
from app.db.phase61_quote_partial_payments_schema_sync import (
    ensure_phase61_quote_partial_payments_foundation,
)
from app.db.phase62_employee_training_schema_sync import (
    ensure_phase62_employee_training_foundation,
)
from app.db.phase63_corporate_tax_schema_sync import (
    ensure_phase63_corporate_tax_foundation,
)
from app.db.phase64_finance_planning_scenarios_schema_sync import (
    ensure_phase64_finance_planning_scenarios_foundation,
)
from app.db.phase65_hr_form_publish_schema_sync import (
    ensure_phase65_hr_form_publish_foundation,
)
from app.db.phase66_stream_numbering_schema_sync import (
    ensure_phase66_stream_numbering_foundation,
)
from app.db.phase67_employee_offboard_schema_sync import (
    ensure_phase67_employee_offboard_foundation,
)
from app.db.phase68_exit_interview_assessment_schema_sync import (
    ensure_phase68_exit_interview_assessment_foundation,
)
from app.db.phase69_commercial_tenancy_schema_sync import (
    ensure_phase69_commercial_tenancy_foundation,
)
from app.db.phase70_tenant_id_schema_sync import ensure_phase70_tenant_id_foundation
from app.db.phase71_tenant_unique_schema_sync import (
    ensure_phase71_tenant_unique_foundation,
)
from app.db.phase72_public_api_webhooks_schema_sync import (
    ensure_phase72_public_api_webhooks_foundation,
)
from app.db.phase73_webhook_retry_schema_sync import ensure_phase73_webhook_retry_foundation
from app.db.phase74_pg_rls_schema_sync import ensure_phase74_pg_rls_foundation
from app.db.phase75_commercial_readiness_schema_sync import (
    ensure_phase75_commercial_readiness_foundation,
)
from app.db.phase76_stream_platform_schema_sync import (
    ensure_phase76_stream_platform_foundation,
)
from app.db.phase77_command_center_schema_sync import (
    ensure_phase77_command_center_foundation,
)
from app.db.phase78_employee_immutable_schema_sync import (
    ensure_phase78_employee_immutable_foundation,
)
from app.db.phase79_timesheet_home_team_schema_sync import (
    ensure_phase79_timesheet_home_team_foundation,
)
from app.db.phase80_post_completion_timesheet_schema_sync import (
    ensure_phase80_post_completion_timesheet_foundation,
)
from app.db.phase81_it_operations_schema_sync import (
    ensure_phase81_it_operations_foundation,
)
from app.db.phase82_it_ownership_schema_sync import (
    ensure_phase82_it_ownership_foundation,
)
from app.db.schema_sync import (
    ensure_admin_schema,
    ensure_design_roles,
    ensure_production_roles,
    ensure_performance_indexes,
    ensure_design_team,
    ensure_project_lifecycle_schema,
    ensure_project_stage_and_execution_status,
    ensure_placeholder_project_schema,
    ensure_project_timestamps,
    ensure_project_template_schema,
    ensure_project_actual_hours,
    ensure_project_health,
    ensure_non_productive_codes,
    ensure_standard_task_types,
    ensure_timesheet_entry_work_category,
    ensure_timesheet_entry_hours_constraint,
    ensure_timesheet_entry_leave_count,
    ensure_timesheet_entry_timestamps,
    ensure_timesheet_entry_soft_delete,
    ensure_timesheet_approval_comments,
    ensure_team_schema,
    ensure_user_team_schema,
    ensure_user_lifecycle_schema,
    ensure_user_auth_schema,
    ensure_user_access_schema,
)
from app.db.session import engine, sessionmaker


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger("protrack.startup")

    from app.core.config import assert_production_security

    for problem in assert_production_security():
        logger.warning("SECURITY: %s", problem)

    Base.metadata.create_all(bind=engine)

    startup_steps = [
        ("project_actual_hours", ensure_project_actual_hours),
        ("project_health", ensure_project_health),
        ("timesheet_approval_comments", ensure_timesheet_approval_comments),
        ("design_roles", ensure_design_roles),
        ("production_roles", ensure_production_roles),
        ("admin_schema", ensure_admin_schema),
        ("project_template_schema", ensure_project_template_schema),
        ("project_lifecycle_schema", ensure_project_lifecycle_schema),
        ("project_stage_and_execution_status", ensure_project_stage_and_execution_status),
        ("placeholder_project_schema", ensure_placeholder_project_schema),
        ("project_timestamps", ensure_project_timestamps),
        ("team_schema", ensure_team_schema),
        ("user_team_schema", ensure_user_team_schema),
        ("user_lifecycle_schema", ensure_user_lifecycle_schema),
        ("user_auth_schema", ensure_user_auth_schema),
        ("user_access_schema", ensure_user_access_schema),
        ("phase15_working_model", ensure_phase15_working_model_foundation),
        ("timesheet_entry_work_category", ensure_timesheet_entry_work_category),
        ("timesheet_entry_hours_constraint", ensure_timesheet_entry_hours_constraint),
        ("timesheet_entry_timestamps", ensure_timesheet_entry_timestamps),
        ("timesheet_entry_soft_delete", ensure_timesheet_entry_soft_delete),
        ("phase16_timesheet_contribution", ensure_phase16_timesheet_contribution_foundation),
        ("non_productive_codes", ensure_non_productive_codes),
        ("timesheet_entry_leave_count", ensure_timesheet_entry_leave_count),
        ("phase14_kpi", ensure_phase14_kpi_foundation),
        ("standard_task_types", ensure_standard_task_types),
        ("phase7", ensure_phase7_foundation),
        ("phase8", ensure_phase8_foundation),
        ("phase9", ensure_phase9_foundation),
        ("phase10_milestone", ensure_phase10_milestone_foundation),
        ("email_foundation", ensure_email_foundation),
        ("email_communication", ensure_email_communication_foundation),
        ("phase13_multi_team", ensure_phase13_multi_team_foundation),
        ("phase17_ebmp_finance", ensure_phase17_ebmp_finance_foundation),
        ("phase18_finance_annual_plan", ensure_phase18_finance_annual_plan_foundation),
        ("phase19_timesheet_report_inclusion", ensure_phase19_timesheet_report_inclusion_foundation),
        ("project_complexity", ensure_project_complexity),
        ("project_workorder_metadata", ensure_project_workorder_metadata),
        ("phase22_finance_rebuild", ensure_phase22_finance_rebuild_foundation),
        ("phase23_finance_team_scope", ensure_phase23_finance_team_scope_foundation),
        ("phase24_user_requires_salary", ensure_phase24_user_requires_salary_foundation),
        ("phase25_expense_purchase_date", ensure_phase25_expense_purchase_date_foundation),
        ("phase26_customer_currency", ensure_phase26_customer_currency_foundation),
        ("phase27_fx_rate_backfill", ensure_phase27_fx_rate_backfill),
        ("phase28_team_member_billable", ensure_phase28_team_member_billable_foundation),
        ("phase29_quote_team", ensure_phase29_quote_team_foundation),
        ("phase30_quote_external_number", ensure_phase30_quote_external_number_foundation),
        ("phase31_overhead_role_billable", ensure_phase31_overhead_role_billable_backfill),
        ("phase32_finance_quarterly_fee_bands", ensure_phase32_finance_quarterly_fee_bands_foundation),
        ("phase33_management_team", ensure_phase33_management_team_foundation),
        ("phase34_quote_quoted_date", ensure_phase34_quote_quoted_date_foundation),
        ("phase35_overhead_team_merge", ensure_phase35_overhead_team_merge_foundation),
        ("phase36_team_membership_periods", ensure_phase36_team_membership_periods_foundation),
        ("phase37_performance_reviews", ensure_phase37_performance_reviews_foundation),
        ("phase38_performance_review_enhancements", ensure_phase38_performance_review_enhancements),
        ("phase39_performance_review_projects", ensure_phase39_performance_review_projects_foundation),
        ("phase40_performance_review_form", ensure_phase40_performance_review_form_foundation),
        ("phase41_performance_review_experience", ensure_phase41_performance_review_experience_foundation),
        ("phase42_performance_skill_matrix", ensure_phase42_performance_skill_matrix_foundation),
        ("phase43_quote_invoiced_date", ensure_phase43_quote_invoiced_date_foundation),
        ("phase44_quote_invoicing", ensure_phase44_quote_invoicing_foundation),
        ("phase45_performance_review_engine", ensure_phase45_performance_review_engine_foundation),
        ("phase46_org_department", ensure_phase46_org_department_foundation),
        ("phase47_user_lifecycle", ensure_phase47_user_lifecycle_foundation),
        ("phase48_compensation_change", ensure_phase48_compensation_change_foundation),
        ("phase49_role_hierarchy", ensure_phase49_role_hierarchy_foundation),
        ("phase50_security_foundation", ensure_phase50_security_foundation),
        ("phase51_department_standardization", ensure_phase51_department_standardization),
        ("phase52_ticketing", ensure_phase52_ticketing_foundation),
        ("phase53_ticket_routing", ensure_phase53_ticket_routing_foundation),
        ("phase54_onboarding", ensure_phase54_onboarding_foundation),
        ("phase55_exit_process", ensure_phase55_exit_process_foundation),
        ("phase56_hr_process_control", ensure_phase56_hr_process_control_foundation),
        ("phase57_background_jobs", ensure_phase57_background_jobs_foundation),
        ("phase58_r3_portfolio", ensure_phase58_r3_portfolio_foundation),
        ("phase59_r4_enterprise", ensure_phase59_r4_enterprise_foundation),
        ("phase60_quote_payment", ensure_phase60_quote_payment_foundation),
        ("phase61_quote_partial_payments", ensure_phase61_quote_partial_payments_foundation),
        ("phase62_employee_training", ensure_phase62_employee_training_foundation),
        ("phase63_corporate_tax", ensure_phase63_corporate_tax_foundation),
        ("phase64_finance_planning_scenarios", ensure_phase64_finance_planning_scenarios_foundation),
        ("phase65_hr_form_publish", ensure_phase65_hr_form_publish_foundation),
        ("phase66_stream_numbering", ensure_phase66_stream_numbering_foundation),
        ("phase67_employee_offboard", ensure_phase67_employee_offboard_foundation),
        ("phase68_exit_interview_assessment", ensure_phase68_exit_interview_assessment_foundation),
        ("phase69_commercial_tenancy", ensure_phase69_commercial_tenancy_foundation),
        ("phase70_tenant_id", ensure_phase70_tenant_id_foundation),
        ("phase71_tenant_unique", ensure_phase71_tenant_unique_foundation),
        ("phase72_public_api_webhooks", ensure_phase72_public_api_webhooks_foundation),
        ("phase73_webhook_retry", ensure_phase73_webhook_retry_foundation),
        ("phase74_pg_rls", ensure_phase74_pg_rls_foundation),
        ("phase75_commercial_readiness", ensure_phase75_commercial_readiness_foundation),
        ("phase76_stream_platform", ensure_phase76_stream_platform_foundation),
        ("phase77_command_center", ensure_phase77_command_center_foundation),
        ("phase78_employee_immutable", ensure_phase78_employee_immutable_foundation),
        ("phase79_timesheet_home_team", ensure_phase79_timesheet_home_team_foundation),
        ("phase80_post_completion_timesheet", ensure_phase80_post_completion_timesheet_foundation),
        ("phase81_it_operations", ensure_phase81_it_operations_foundation),
        ("phase82_it_ownership", ensure_phase82_it_ownership_foundation),
        ("performance_indexes", ensure_performance_indexes),
    ]

    failures: list[str] = []
    for name, step in startup_steps:
        try:
            step(engine)
        except Exception:
            failures.append(name)
            logger.exception("Startup schema step failed: %s", name)

    if ENABLE_DEMO_SEED:
        try:
            ensure_design_team(engine)
        except Exception:
            failures.append("design_team_seed")
            logger.exception("Demo design team seed failed")

    seed_session = sessionmaker(bind=engine)()
    try:
        ensure_engineering_streams(seed_session)
        seed_session.commit()
        ensure_project_types_and_templates(seed_session)
        validate_project_template_health(seed_session)
    except Exception:
        seed_session.rollback()
        failures.append("project_template_seed")
        logger.exception("Project template seed/validation failed")
    finally:
        seed_session.close()

    if failures:
        logger.error(
            "ProTrack API started with schema step failures: %s. "
            "Login/API may still work; fix and restart before release.",
            ", ".join(failures),
        )
    else:
        logger.info("ProTrack API startup schema sync completed successfully")

    # Best-effort: store today's live FX so quote/expense writes lock current market rates.
    try:
        from app.services.finance.fx_live_service import live_fx_enabled, refresh_live_fx_rates

        if live_fx_enabled():
            fx_session = sessionmaker(bind=engine)()
            try:
                summary = refresh_live_fx_rates(fx_session)
                fx_session.commit()
                logger.info(
                    "Live FX refresh %s: +%s new, ~%s updated, fail=%s",
                    summary.get("effective_date"),
                    summary.get("created"),
                    summary.get("updated"),
                    summary.get("failed") or "-",
                )
            except Exception:
                fx_session.rollback()
                logger.exception("Live FX refresh skipped (seed/manual rates still apply)")
            finally:
                fx_session.close()
    except Exception:
        logger.exception("Live FX module unavailable at startup")

    lifecycle_session = sessionmaker(bind=engine)()
    try:
        from app.services.employee_offboard_service import apply_due_offboards
        from app.services.user_change_service import (
            apply_due_compensation,
            apply_due_lifecycle,
        )

        apply_due_lifecycle(lifecycle_session)
        apply_due_compensation(lifecycle_session)
        apply_due_offboards(lifecycle_session)
        lifecycle_session.commit()
    except Exception:
        lifecycle_session.rollback()
        logger.exception("Apply-due lifecycle / compensation / offboard sweep failed")
    finally:
        lifecycle_session.close()

    commercial_session = sessionmaker(bind=engine)()
    try:
        from app.models.commercial import PROSOHM_TENANT_ID
        from app.services import feature_flag_service, tenant_service

        tenant_service.ensure_prosohm_tenant(commercial_session)
        from app.services import tenant_pack_service

        tenant_pack_service.ensure_tenant_config_defaults(commercial_session)
        feature_flag_service.ensure_tenant_flags(commercial_session, PROSOHM_TENANT_ID)
        commercial_session.commit()
    except Exception:
        commercial_session.rollback()
        logger.exception("Commercial tenant / feature-flag seed failed")
    finally:
        commercial_session.close()

    reminder_session = sessionmaker(bind=engine)()
    try:
        from app.services.finance.quote_invoicing_notifier import notify_uninvoiced_quotes
        from app.services.finance.quote_payment_notifier import notify_unpaid_quotes

        notify_uninvoiced_quotes(reminder_session)
        notify_unpaid_quotes(reminder_session)
        reminder_session.commit()
    except Exception:
        reminder_session.rollback()
        logger.exception("Quote invoicing / payment reminder step failed")
    finally:
        reminder_session.close()

    yield


app = FastAPI(
    title="ProTrack API",
    description="Engineering management platform API for Prosohm Projects Pvt. Ltd.",
    version=f"{APP_VERSION}-{RELEASE_CANDIDATE.lower()}",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": False,
    },
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description or "",
        routes=app.routes,
    )
    app.openapi_schema = fix_ref_siblings(schema)
    return app.openapi_schema


app.openapi = custom_openapi

# --- Rate limiting ----------------------------------------------------------
# Imported via app.core.rate_limit so a missing slowapi degrades gracefully
# instead of crashing startup.
from app.core.rate_limit import (
    RateLimitExceeded,
    limiter,
    rate_limit_exceeded_handler,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# --- Middleware (outermost first) -------------------------------------------
from app.core.config import TRUSTED_HOSTS
from app.core.security_middleware import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if TRUSTED_HOSTS:
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

app.include_router(api_router, prefix="/api/v1")
app.include_router(public_api_router, prefix="/api/public/v1")

# The uploads directory is intentionally NOT mounted as a public static route.
# Serving it unauthenticated exposed every stored file (and enabled stored-XSS
# via uploaded SVGs). The only public asset — the company logo — is served
# through the permission-aware /api/v1/settings/company/logo endpoint instead.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
if not os.access(UPLOAD_DIR, os.W_OK):
    import logging

    logging.getLogger("protrack.startup").warning(
        "PROTRACK_UPLOAD_DIR is not writable: %s — set a persistent volume path in production.",
        UPLOAD_DIR,
    )


@app.get("/health")
def health_check():
    """Load-balancer friendly health: shallow DB ping + upload dir writable."""
    from sqlalchemy import text

    from app.core.config import UPLOAD_DIR as _upload_dir
    from app.db.session import SessionLocal

    checks: dict[str, object] = {
        "database": "ok",
        "upload_dir_writable": True,
    }
    status = "ok"
    try:
        db = SessionLocal()
        try:
            db.scalar(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
        status = "degraded"

    try:
        _upload_dir.mkdir(parents=True, exist_ok=True)
        probe = _upload_dir / ".health_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        checks["upload_dir_writable"] = False
        checks["upload_dir_error"] = exc.__class__.__name__
        if status == "ok":
            status = "degraded"

    return {
        "status": status,
        "app": "ProTrack",
        "version": APP_VERSION,
        "release": RELEASE_CANDIDATE,
        "internal_release": INTERNAL_RELEASE,
        "checks": checks,
    }
