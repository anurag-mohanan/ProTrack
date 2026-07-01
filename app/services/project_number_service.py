"""Customer-specific project numbering."""

from sqlalchemy.orm import Session

from app.models.models import Customer


def generate_project_code(db: Session, customer: Customer, tool_number: str) -> str:
    fmt = customer.project_number_format or "{tool_number}"
    prefix = customer.project_number_prefix or customer.code or ""
    sequence = customer.next_project_sequence or 1

    code = fmt.format(
        tool_number=tool_number,
        prefix=prefix,
        seq=sequence,
        customer_code=customer.code or "",
    ).strip()

    customer.next_project_sequence = sequence + 1
    db.add(customer)
    return code
