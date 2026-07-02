import pytest

from app.core.field_normalization import normalize_optional_text
from app.schemas.identity import UserUpdate
from app.schemas.organization import ContactUpdate, CustomerUpdate


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("#VALUE", None),
        ("#VALUE!", None),
        ("#N/A", None),
        ("undefined", None),
        ("null", None),
        ("NaN", None),
        ("[object Object]", None),
        ("  Sybridge  ", "Sybridge"),
    ],
)
def test_normalize_optional_text(raw, expected):
    assert normalize_optional_text(raw) == expected


def test_user_update_blank_optional_fields_become_null():
    payload = UserUpdate(phone="", designation="#VALUE", manager_id=None)
    assert payload.phone is None
    assert payload.designation is None


def test_customer_update_optional_strings():
    payload = CustomerUpdate(code="", notes="#VALUE", project_number_prefix="  TI  ")
    assert payload.code is None
    assert payload.notes is None
    assert payload.project_number_prefix == "TI"


def test_contact_update_optional_email():
    payload = ContactUpdate(email="", phone="555-0100")
    assert payload.email is None
    assert payload.phone == "555-0100"
