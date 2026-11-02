"""Receivables and customer finance for quotes linked to a project (B0.x: ``project.name`` does not exist).

The project description shown next to the tool number is ``Project.part_description``. Amounts,
FIFO allocation and aging buckets must be exactly what they were for an unlinked quote.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.finance import QuotePaymentLine
from app.services.finance.customer_financial_service import (
    aggregate_customer_financial_summary,
    project_financial_summary,
)
from app.services.finance.receivables_service import build_receivables_aging
from tests.test_engineering_metrics import _project
from tests.test_forecasting import IDS, _finance_team, _invoice, _quote

TODAY = date(2030, 3, 15)


def _ledger(session, team, *, project_id=None):
    quote = _quote(session, team, awarded="1000", project_id=project_id)
    _invoice(session, quote, "100", date(2030, 1, 10), date(2030, 2, 10))  # 33 days overdue
    _invoice(session, quote, "200", date(2030, 2, 1), date(2030, 4, 20))  # not yet due
    session.add(QuotePaymentLine(quote_id=quote.id, amount=Decimal("30"), line_date=date(2030, 2, 20)))
    session.flush()
    return quote


def test_receivables_for_a_project_linked_quote_show_the_part_description(session):
    team = _finance_team(session)
    project = _project(session, team_id=team.id)
    linked = _ledger(session, team, project_id=project.id)
    session.commit()

    aging = build_receivables_aging(session, team_id=team.id, today=TODAY)

    rows = [r for r in aging["rows"] if r["quote_id"] == str(linked.id)]
    assert [r["project_name"] for r in rows] == ["Metrics part", "Metrics part"]
    assert all(r["project_id"] == str(project.id) for r in rows)
    assert all(r["tool_number"] == linked.tool_number for r in rows)


def test_linking_a_project_does_not_change_amounts_or_buckets(session):
    unlinked_team, linked_team = _finance_team(session), _finance_team(session)
    _ledger(session, unlinked_team)
    project = _project(session, team_id=linked_team.id)
    _ledger(session, linked_team, project_id=project.id)
    session.commit()

    unlinked = build_receivables_aging(session, team_id=unlinked_team.id, today=TODAY)
    linked = build_receivables_aging(session, team_id=linked_team.id, today=TODAY)

    for key in ("total_outstanding", "overdue", "not_yet_due", "due_soon", "due_today", "buckets"):
        assert linked[key] == unlinked[key], key
    assert linked["total_outstanding"] == Decimal("270.00")  # FIFO: 30 paid against the first line
    assert linked["buckets"]["31_60_overdue"] == Decimal("70.00")
    assert linked["buckets"]["not_yet_due"] == Decimal("200.00")
    assert [r["outstanding"] for r in linked["rows"]] == [r["outstanding"] for r in unlinked["rows"]]


def test_customer_and_project_finance_summaries_show_the_part_description(session):
    team = _finance_team(session)
    project = _project(session, team_id=team.id)
    quote = _ledger(session, team, project_id=project.id)
    session.commit()

    customer = aggregate_customer_financial_summary(session, customer_id=IDS["customer"], team_id=team.id, today=TODAY)
    [row] = [q for q in customer["quotes"] if q["quote_id"] == str(quote.id)]
    assert row["project_name"] == "Metrics part"
    assert row["invoiced"] == Decimal("300.00") and row["paid"] == Decimal("30.00")

    summary = project_financial_summary(session, project_id=project.id, team_id=team.id)
    assert summary["project_name"] == "Metrics part"
    assert summary["invoiced"] == Decimal("300.00") and summary["collected"] == Decimal("30.00")


def test_receivables_api_returns_project_linked_rows(client, session):
    team = _finance_team(session)
    project = _project(session, team_id=team.id)
    _ledger(session, team, project_id=project.id)
    session.commit()

    response = client.get("/api/v1/finance/receivables", params={"team_id": str(team.id)}, headers=client.auth_headers)

    assert response.status_code == 200, response.text
    assert {r["project_name"] for r in response.json()["rows"]} == {"Metrics part"}
