"""Quote PDF extract → review → confirm (Wave 1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch
import uuid

from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Team, User
from app.services.finance.quote_pdf_import_service import (
    confirm_quote_pdf_import,
    extract_quote_pdf,
)
from sqlalchemy import select
from tests.conftest import IDS
from tests.test_prosohm_quote_pdf_import import GOLDEN_QT_TEXT


def test_extract_quote_pdf_does_not_create_quote(session):
    team = Team(id=uuid.uuid4(), name="QT PDF Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Sybridge Technologies Canada Inc-MIS",
        code=f"SY{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.commit()

    with patch(
        "app.services.finance.quote_pdf_import_service.extract_prosohm_quote_text",
        return_value=GOLDEN_QT_TEXT,
    ):
        extracted = extract_quote_pdf(
            session,
            content=b"%PDF-fake",
            filename="QT-2026-27-001.pdf",
            team_id=team.id,
        )

    assert extracted["text_extractable"] is True
    assert extracted["ocr_used"] is False
    assert extracted["fields"]["external_quote_number"]["value"] == "QT-2026-27-001"
    assert extracted["fields"]["tool_number"]["value"] == "17974"
    assert extracted["fields"]["quoted_revenue"]["value"]
    assert extracted["suggested_customer_id"] == str(customer.id)
    assert session.scalars(select(Quote)).first() is None


def test_confirm_quote_pdf_creates_quote(session):
    team = Team(id=uuid.uuid4(), name="QT Confirm Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Sybridge Technologies Canada Inc-MIS",
        code=f"SY{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.commit()
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None

    outcome = confirm_quote_pdf_import(
        session,
        team_id=team.id,
        customer_id=customer.id,
        tool_number="17974",
        quoted_revenue=Decimal("6160.00"),
        external_quote_number="QT-2026-27-001",
        currency_code="USD",
        quoted_hours=Decimal("220"),
        quoted_date=date(2026, 4, 10),
        create_project=False,
        import_anyway=False,
        notes=None,
        content=None,
        filename=None,
        content_sha256=None,
        user=admin,
    )
    session.commit()
    assert outcome.quote.tool_number == "17974"
    assert outcome.quote.external_quote_number == "QT-2026-27-001"
    rev = session.scalars(
        select(QuoteRevision).where(QuoteRevision.quote_id == outcome.quote.id)
    ).first()
    assert rev is not None
    assert rev.quoted_revenue == Decimal("6160.00")


def test_confirm_blocks_duplicate_without_import_anyway(session):
    team = Team(id=uuid.uuid4(), name="QT Dup Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Dup QT Customer",
        code=f"DQ{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number="17974",
        external_quote_number="QT-2026-27-001",
        currency_code="USD",
        is_active=True,
    )
    session.add(quote)
    session.commit()
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None

    from app.core.exceptions import ProTrackValidationError
    import pytest

    with pytest.raises(ProTrackValidationError, match="duplicate"):
        confirm_quote_pdf_import(
            session,
            team_id=team.id,
            customer_id=customer.id,
            tool_number="17974",
            quoted_revenue=Decimal("6160.00"),
            external_quote_number="QT-2026-27-001",
            currency_code="USD",
            quoted_hours=Decimal("220"),
            quoted_date=date(2026, 4, 10),
            create_project=False,
            import_anyway=False,
            notes=None,
            content=None,
            filename=None,
            content_sha256=None,
            user=admin,
        )
