"""Project communication helpers and one-click email actions."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.foundation import get_or_create_company_settings
from app.models.models import Contact, Customer, Project, User
from app.services.email.engine import EmailService

ONE_CLICK_ACTIONS = {
    "notify_designer": ("project_assigned", "Notify Designer"),
    "notify_customer": ("customer_project_update", "Notify Customer"),
    "notify_team": ("resource_allocation", "Notify Team"),
    "request_update": ("project_status", "Request Update"),
    "request_review": ("management_notification", "Request Review"),
    "send_release": ("files_released", "Send Release"),
}

CUSTOMER_EMAIL_TEMPLATES = {
    "project_status": "Project Status",
    "progress_update": "Progress Update",
    "files_released": "Files Released",
    "delay_notification": "Delay Notification",
    "meeting_summary": "Meeting Summary",
    "quote": "Quote",
    "engineering_change_notice": "Engineering Change Notice",
}


def _user_display(user: User | None) -> str:
    if user is None:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "")


def build_project_email_context(db: Session, project: Project, *, message: str = "") -> dict[str, str]:
    customer = db.get(Customer, project.customer_id)
    contact = (
        db.get(Contact, project.customer_contact_id) if project.customer_contact_id else None
    )
    designer = db.get(User, project.designer_id) if project.designer_id else None
    surfacer = db.get(User, project.surfacer_id) if project.surfacer_id else None
    design_leader = (
        db.get(User, project.design_leader_id) if project.design_leader_id else None
    )
    company = get_or_create_company_settings(db)
    quoted = Decimal(str(project.quoted_hours or 0))
    actual = Decimal(str(project.actual_hours or 0))
    variance = actual - quoted
    return {
        "Designer": _user_display(designer),
        "Surfacer": _user_display(surfacer),
        "DesignLeader": _user_display(design_leader),
        "Customer": customer.name if customer else "",
        "CustomerContact": f"{contact.first_name} {contact.last_name}".strip() if contact else "",
        "ToolNumber": project.tool_number,
        "PartDescription": project.part_description,
        "ProjectStage": project.project_stage.value if project.project_stage else "",
        "ProjectStatus": project.execution_status.value if project.execution_status else "",
        "DueDate": project.due_date.isoformat() if project.due_date else "",
        "Milestone": "",
        "QuotedHours": f"{quoted:.2f}",
        "ActualHours": f"{actual:.2f}",
        "Variance": f"{variance:.2f}",
        "Company": company.company_name or "ProTrack",
        "Manager": _user_display(design_leader),
        "Message": message,
    }


def resolve_project_attachment_paths(project: Project, *, include_released: bool = False) -> list[str]:
    paths: list[str] = []
    for folder in (project.project_folder_path, project.cad_folder_path):
        if not folder:
            continue
        folder_path = Path(folder)
        if not folder_path.is_dir():
            continue
        for entry in folder_path.iterdir():
            if entry.is_file():
                paths.append(str(entry))
    if include_released and project.released_folder_path:
        released = Path(project.released_folder_path)
        if released.is_dir():
            for entry in released.iterdir():
                if entry.is_file():
                    paths.append(str(entry))
    return paths[:10]


def send_one_click_email(
    db: Session,
    *,
    project_id: UUID,
    action: str,
    sent_by_user_id: UUID,
    message: str = "",
    extra_addresses: list[str] | None = None,
    attach_released_files: bool = False,
) -> bool:
    if action not in ONE_CLICK_ACTIONS:
        raise ValueError(f"Unknown one-click action: {action}")
    template_slug, timeline_label = ONE_CLICK_ACTIONS[action]
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    context = build_project_email_context(db, project, message=message)
    addresses = list(extra_addresses or [])
    if action == "notify_designer" and project.designer_id:
        designer = db.get(User, project.designer_id)
        if designer and designer.email:
            addresses.append(designer.email)
    if action == "notify_customer":
        if project.customer_contact_id:
            contact = db.get(Contact, project.customer_contact_id)
            if contact and contact.email:
                addresses.append(contact.email)
    if action == "notify_team":
        for user_id in (project.designer_id, project.surfacer_id, project.design_leader_id):
            if user_id:
                user = db.get(User, user_id)
                if user and user.email:
                    addresses.append(user.email)

    addresses = list(dict.fromkeys(address for address in addresses if address))
    if not addresses:
        raise ValueError("No recipient email addresses could be resolved for this action.")

    attachment_paths = (
        resolve_project_attachment_paths(project, include_released=attach_released_files)
        if attach_released_files or action == "send_release"
        else None
    )
    return EmailService(db).send_templated_email(
        template_slug=template_slug,
        to_addresses=addresses,
        context=context,
        project_id=project.id,
        sent_by_user_id=sent_by_user_id,
        attachment_paths=attachment_paths,
        timeline_label=timeline_label,
    )


def send_customer_template_email(
    db: Session,
    *,
    project_id: UUID,
    template_slug: str,
    sent_by_user_id: UUID,
    message: str,
    to_addresses: list[str] | None = None,
    attachment_paths: list[str] | None = None,
) -> bool:
    if template_slug not in CUSTOMER_EMAIL_TEMPLATES:
        raise ValueError(f"Unknown customer template: {template_slug}")
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    addresses = list(to_addresses or [])
    if project.customer_contact_id:
        contact = db.get(Contact, project.customer_contact_id)
        if contact and contact.email:
            addresses.append(contact.email)
    addresses = list(dict.fromkeys(address for address in addresses if address))
    if not addresses:
        raise ValueError("At least one customer email address is required.")

    context = build_project_email_context(db, project, message=message)
    return EmailService(db).send_templated_email(
        template_slug=template_slug,
        to_addresses=addresses,
        context=context,
        project_id=project.id,
        sent_by_user_id=sent_by_user_id,
        attachment_paths=attachment_paths,
        timeline_label=CUSTOMER_EMAIL_TEMPLATES[template_slug],
    )
