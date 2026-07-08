"""Template placeholder rendering."""

from __future__ import annotations

import re
from typing import Any

from app.models.foundation import EmailTemplate

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")

EMAIL_TEMPLATE_VARIABLES = [
    "Designer",
    "Surfacer",
    "DesignLeader",
    "Customer",
    "CustomerContact",
    "ToolNumber",
    "PartDescription",
    "ProjectStage",
    "ProjectStatus",
    "DueDate",
    "Milestone",
    "QuotedHours",
    "ActualHours",
    "Variance",
    "Company",
    "Manager",
    "Message",
    "Title",
    "Period",
    "Notes",
    "Summary",
    "ImportName",
    "ResetLink",
    "LoginUrl",
]


def render_template_content(content: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, context.get(key.lower(), ""))
        return "" if value is None else str(value)

    return _PLACEHOLDER_PATTERN.sub(replace, content)


def render_email_template(
    template: EmailTemplate,
    context: dict[str, Any],
) -> tuple[str, str, str | None]:
    subject = render_template_content(template.subject, context)
    html = render_template_content(template.body_html, context)
    text = (
        render_template_content(template.body_text, context)
        if template.body_text
        else None
    )
    return subject, html, text


def preview_template(
    *,
    subject: str,
    body_html: str,
    body_text: str | None,
    context: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "subject": render_template_content(subject, context),
        "body_html": render_template_content(body_html, context),
        "body_text": render_template_content(body_text, context) if body_text else None,
    }
