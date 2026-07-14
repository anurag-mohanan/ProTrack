from app.services.workorder_pdf_extract import extract_workorder_fields_from_text


def test_extract_workorder_label_value_pairs():
    text = """
    Customer Work Order: CMT-WO-7788
    Part Description: Frt Door Main Panel L/R
    Press Tonnage: 650 T
    Plastic Material: PP GF30
    Cavity: 2
    Tool Type: Injection mould
    Specifications: Gate from runner side
    """
    result = extract_workorder_fields_from_text(text)
    assert result.work_order_number == "CMT-WO-7788"
    assert "Door" in (result.part_description or "")
    assert result.press_tonnage == "650T"
    assert result.plastic_material == "PP GF30"
    assert result.cavity_count == 2
    assert result.tool_type and "Injection" in result.tool_type
    assert result.customer_specs and "Gate" in result.customer_specs


def test_extract_workorder_loose_patterns():
    text = "WO No 4412 Material ABS Tonnage 400ton Cavities 1"
    result = extract_workorder_fields_from_text(text)
    assert result.work_order_number == "4412"
    assert result.plastic_material and "ABS" in result.plastic_material
    assert result.press_tonnage == "400T"
    assert result.cavity_count == 1


def test_stdlib_pdf_scrape_reads_literals():
    from app.services.workorder_pdf_extract import _extract_text_stdlib, extract_workorder_fields_from_pdf

    # Minimal PDF-ish bytes with literal strings — no pdfplumber required.
    content = b"""%PDF-1.4
BT (Work Order: WO-7788) Tj (Press Tonnage: 650 T) Tj (Plastic Material: PP GF30) Tj (Cavity: 2) Tj ET
%%EOF
"""
    text = _extract_text_stdlib(content)
    assert "WO-7788" in text or "Work Order" in text

    result = extract_workorder_fields_from_pdf(content)
    assert result.work_order_number == "WO-7788"
    assert result.press_tonnage == "650T"
    assert result.plastic_material == "PP GF30"
    assert result.cavity_count == 2
