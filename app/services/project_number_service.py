"""Customer- and stream-specific project numbering."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Customer, Stream


def generate_project_code(db: Session, customer: Customer, tool_number: str) -> str:
    fmt = customer.project_number_format or "{tool_number}"
    prefix = customer.project_number_prefix or customer.code or ""
    sequence = customer.next_project_sequence or 1

    code = fmt.format(
        tool_number=tool_number,
        prefix=prefix,
        seq=sequence,
        customer_code=customer.code or "",
        year=datetime.utcnow().year,
    ).strip()

    customer.next_project_sequence = sequence + 1
    db.add(customer)
    return code


def preview_stream_project_code(
    stream: Stream,
    *,
    tool_number: str = "TOOL-001",
) -> str | None:
    """Return a sample code for UI helpers without consuming the sequence."""
    if not stream.use_project_numbering and not stream.use_project_prefix:
        return None

    prefix = (stream.project_number_prefix or "").strip() if stream.use_project_prefix else ""
    sequence = stream.next_project_sequence or 1
    year = datetime.utcnow().year

    if stream.use_project_numbering:
        fmt = (stream.project_number_format or "").strip() or (
            "{prefix}-{seq}" if prefix else "{seq}"
        )
        try:
            code = fmt.format(
                tool_number=tool_number,
                prefix=prefix,
                seq=sequence,
                year=year,
            ).strip()
        except (KeyError, ValueError):
            code = f"{prefix}-{sequence}" if prefix else str(sequence)
        return code.replace("--", "-").strip("-") or str(sequence)

    if prefix:
        return f"{prefix}-{tool_number}".replace("--", "-").strip("-")
    return None


def generate_stream_project_code(db: Session, stream: Stream, tool_number: str) -> str | None:
    """Generate a project code from stream settings; bumps sequence when numbering is on."""
    preview = preview_stream_project_code(stream, tool_number=tool_number)
    if preview is None:
        return None

    if stream.use_project_numbering:
        sequence = stream.next_project_sequence or 1
        stream.next_project_sequence = sequence + 1
        db.add(stream)

    return preview
