"""Editing team commercial terms with fee bands (regression for PUT 500)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta


def _make_retainer(session):
    from app.models.enums import WorkingModelCode
    from app.models.models import Team, WorkingModel

    team = Team(id=uuid.uuid4(), name=f"Edit Terms {uuid.uuid4().hex[:6]}", is_active=True)
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"retainer_{uuid.uuid4().hex[:8]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Edit",
        is_active=True,
    )
    session.add(team)
    session.add(model)
    session.commit()
    return team, model


def test_edit_team_commercial_with_fee_bands_and_future_date(client, auth_headers, session):
    """Editing terms (PUT) must accept fee bands and a future effective date."""
    team, model = _make_retainer(session)

    create = client.post(
        "/api/v1/finance/team-commercial",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "customer_fee_amount": "3000",
            "currency_code": "USD",
            "billing_period": "monthly",
            "effective_from": date.today().isoformat(),
            "fee_bands": [
                {"skill_level": "", "fee_amount": "3000", "currency_code": "USD"},
            ],
        },
    )
    assert create.status_code == 201, f"CREATE {create.status_code}: {create.text}"
    terms_id = create.json()["id"]

    future = (date.today() + timedelta(days=2)).isoformat()
    edit = client.put(
        f"/api/v1/finance/team-commercial/{terms_id}",
        headers=auth_headers,
        json={
            "team_id": str(team.id),
            "working_model_id": str(model.id),
            "customer_fee_amount": "3200",
            "currency_code": "USD",
            "billing_period": "monthly",
            "effective_from": future,
            "fee_bands": [
                {"skill_level": "", "fee_amount": "3200", "currency_code": "USD"},
                {"skill_level": "advanced", "fee_amount": "4000", "currency_code": "USD"},
            ],
        },
    )
    assert edit.status_code == 200, f"EDIT {edit.status_code}: {edit.text}"
    body = edit.json()
    assert body["effective_from"] == future
    assert len(body["fee_bands"]) == 2
