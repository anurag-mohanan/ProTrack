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
