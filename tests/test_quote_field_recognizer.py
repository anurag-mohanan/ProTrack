"""Awarded quote AI field recognition."""

from __future__ import annotations

from app.services.finance.quote_field_recognizer import (
    enrich_import_row,
    recognize_from_filename,
    recognize_header_key,
    recognize_table_row,
)


def test_recognize_prosohm_headers():
    assert recognize_header_key("Prepared For") == "customer"
    assert recognize_header_key("Customer Project #") == "tool_number"
    assert recognize_header_key("Qty/Hrs") == "quoted_hours"
    assert recognize_header_key("Amount") == "quoted_revenue"
    assert recognize_header_key("Quote Date") == "start_date"
    assert recognize_header_key("Quote#") == "external_quote_number"


def test_recognize_table_row_synonyms():
    row = recognize_table_row(
        {
            "Prepared For": "Acme Inc",
            "Customer Project #": "17974",
            "Qty/Hrs": "220",
            "Amount": "6160",
            "Currency": "USD",
        }
    )
    assert row["customer"] == "Acme Inc"
    assert row["tool_number"] == "17974"
    assert row["quoted_hours"] == "220"
    assert row["quoted_revenue"] == "6160"


def test_recognize_from_filename():
    out = recognize_from_filename("QT-2026-27-001-SY#17974.pdf")
    assert out["external_quote_number"] == "QT-2026-27-001"
    assert out["tool_number"] == "17974"


def test_enrich_fills_tool_from_filename():
    row = enrich_import_row(
        {"Customer": "Acme", "Quoted Hours": "10", "Quoted Revenue": "100"},
        filename="QT-2026-27-009-SY#18888.pdf",
    )
    assert row["tool_number"] == "18888"
    assert row["external_quote_number"] == "QT-2026-27-009"


def test_ai_module_registered():
    from app.services.ai.engine import ai_engine

    assert "quote_import_field_recognizer" in ai_engine._modules
