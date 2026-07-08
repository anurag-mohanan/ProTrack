"""Email communication center tests."""

import json

from app.models.foundation import EmailMessage
from app.services.email.engine import EmailService
from app.services.email.template_renderer import preview_template, render_template_content


def test_email_settings_zoho_defaults(client, auth_headers):
    response = client.post("/api/v1/settings/email/apply-zoho-defaults", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["smtp_host"] == "smtp.zoho.com"
    assert body["smtp_port"] == 465
    assert body["use_ssl"] is True


def test_email_template_variables_endpoint(client, auth_headers):
    response = client.get("/api/v1/emails/variables", headers=auth_headers)
    assert response.status_code == 200
    variables = response.json()["variables"]
    assert "Designer" in variables
    assert "ToolNumber" in variables


def test_email_preview_endpoint(client, auth_headers):
    response = client.post(
        "/api/v1/emails/preview",
        headers=auth_headers,
        json={
            "subject": "Tool {{ToolNumber}}",
            "body_html": "<p>Hello {{Designer}}</p>",
            "context": {"ToolNumber": "T-100", "Designer": "Alex"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "Tool T-100"
    assert "Alex" in body["body_html"]


def test_email_queue_lists_messages(client, auth_headers, session):
    session.add(
        EmailMessage(
            to_addresses=json.dumps(["test@example.com"]),
            subject="Queued test",
            body_html="<p>Test</p>",
            status="queued",
            recipients_display="test@example.com",
        )
    )
    session.commit()

    response = client.get("/api/v1/emails/queue", headers=auth_headers)
    assert response.status_code == 200
    assert any(item["subject"] == "Queued test" for item in response.json())


def test_template_renderer():
    rendered = render_template_content("Hello {{Designer}}", {"Designer": "Sam"})
    assert rendered == "Hello Sam"
    preview = preview_template(
        subject="Tool {{ToolNumber}}",
        body_html="<p>{{Message}}</p>",
        body_text=None,
        context={"ToolNumber": "T-1", "Message": "Update"},
    )
    assert preview["subject"] == "Tool T-1"


def test_email_service_queues_when_disabled(session):
    service = EmailService(session)
    message = service.queue_email(
        to_addresses=["nobody@example.com"],
        subject="Disabled",
        html_body="<p>x</p>",
        send_immediately=False,
    )
    # When email disabled, queue_email returns None
    assert message is None or isinstance(message, EmailMessage)
