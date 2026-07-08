"""Scheduled engineering digest emails."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.foundation import get_or_create_company_settings
from app.models.foundation import UserPreferences
from app.models.models import Role, User
from app.services.email.engine import EmailService

logger = logging.getLogger(__name__)


def _engineering_manager_emails(db: Session) -> list[str]:
    rows = db.execute(
        select(User.email)
        .join(Role, Role.id == User.role_id)
        .where(Role.name.in_(["Engineering Manager", "Admin"]), User.email.is_not(None))
    ).all()
    return [row[0] for row in rows if row[0]]


def _user_wants_digest(db: Session, user: User, preference_field: str) -> bool:
    prefs = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    if prefs is None:
        return True
    return bool(getattr(prefs, preference_field, True))


def queue_daily_engineering_summary(db: Session) -> int:
    from app.services.dashboard_service import get_attention_projects, get_designer_availability

    emails = _engineering_manager_emails(db)
    if not emails:
        return 0
    attention = get_attention_projects(db)
    _, availability_rows = get_designer_availability(db)
    overloaded = [item for item in availability_rows if float(item.utilization_percent) >= 100]
    available = [item for item in availability_rows if float(item.utilization_percent) < 70]
    company = get_or_create_company_settings(db)
    context = {
        "Company": company.company_name or "ProTrack",
        "Period": date.today().isoformat(),
        "Summary": (
            f"Projects needing attention: {len(attention)}; "
            f"Overloaded designers: {len(overloaded)}; "
            f"Available designers: {len(available)}."
        ),
        "Message": "Morning engineering summary attached below.",
    }
    service = EmailService(db)
    message = service.queue_email(
        to_addresses=emails,
        subject=f"Morning Engineering Summary — {context['Period']}",
        html_body=(
            "<p><strong>Morning Engineering Summary</strong></p>"
            f"<p>{context['Summary']}</p>"
            "<p>Review ProTrack for AI insights and detailed drill-down.</p>"
        ),
        text_body=context["Summary"],
        template_slug="daily_engineering_summary",
        timeline_label="Daily Engineering Summary",
        send_immediately=True,
    )
    return 1 if message and message.status == "sent" else 0


def queue_weekly_engineering_summary(db: Session) -> int:
    from app.services.reporting.engine import ReportingEngine

    emails = _engineering_manager_emails(db)
    if not emails:
        return 0
    engine = ReportingEngine()
    payload = engine.build_report(db, report_id="weekly-engineering", period_type="weekly")
    company = get_or_create_company_settings(db)
    context = {
        "Company": company.company_name or "ProTrack",
        "Period": f"Week of {date.today().isoformat()}",
        "Summary": (
            f"Hours worked: {payload.executive.total_engineering_hours}; "
            f"Utilization: {payload.executive.utilization_percent}%."
        ),
        "Message": "Weekly engineering performance summary.",
    }
    service = EmailService(db)
    message = service.queue_email(
        to_addresses=emails,
        subject="Engineering Performance Summary",
        html_body=f"<p><strong>Weekly Engineering Performance</strong></p><p>{context['Summary']}</p>",
        text_body=context["Summary"],
        template_slug="weekly_engineering_summary",
        timeline_label="Weekly Engineering Summary",
        send_immediately=True,
    )
    return 1 if message and message.status == "sent" else 0


def queue_monthly_engineering_report(db: Session) -> int:
    from app.services.reporting.engine import ReportingEngine

    emails = _engineering_manager_emails(db)
    if not emails:
        return 0
    engine = ReportingEngine()
    payload = engine.build_report(db, report_id="monthly-engineering", period_type="monthly")
    workbook_bytes = engine.export_excel(payload)
    company = get_or_create_company_settings(db)
    context = {
        "Company": company.company_name or "ProTrack",
        "Period": date.today().strftime("%B %Y"),
        "Summary": (
            f"Monthly report generated ({len(workbook_bytes)} bytes). "
            f"Hours: {payload.executive.total_engineering_hours}."
        ),
        "Message": "Please find the monthly engineering report in ProTrack reporting.",
    }
    service = EmailService(db)
    message = service.queue_email(
        to_addresses=emails,
        subject=f"Monthly Engineering Report — {context['Period']}",
        html_body=(
            "<p><strong>Monthly Engineering Report</strong></p>"
            "<p>The monthly engineering report has been generated in ProTrack.</p>"
            f"<p>{context['Summary']}</p>"
        ),
        text_body=context["Summary"],
        template_slug="monthly_engineering_report",
        timeline_label="Monthly Engineering Report",
        send_immediately=True,
    )
    return 1 if message and message.status == "sent" else 0
