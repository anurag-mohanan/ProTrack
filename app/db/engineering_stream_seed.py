"""Ensure standard engineering streams exist for skill matrices and user profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Stream

DEFAULT_ENGINEERING_STREAMS: list[tuple[str, str]] = [
    ("Mold Design", "Mold design engineering stream"),
    ("CAD Development", "CAD / product design engineering stream"),
    ("Fixture Design", "Fixture design engineering stream"),
    ("Electrode Design", "Electrode design engineering stream"),
    ("Product Design", "Product design engineering stream"),
    ("Die Casting Design", "Die casting design engineering stream"),
    ("CAM Programming", "CAM programming stream"),
    ("BIW Design", "Body-in-white design stream"),
    ("Plastic Design", "Plastic / injection tooling stream"),
    ("Checking / QC", "Checking and quality control stream"),
]


def ensure_engineering_streams(db: Session) -> int:
    existing = {
        stream.name.strip().lower(): stream
        for stream in db.scalars(select(Stream)).all()
    }
    created = 0
    for name, description in DEFAULT_ENGINEERING_STREAMS:
        key = name.strip().lower()
        if key in existing:
            stream = existing[key]
            if not stream.is_active:
                stream.is_active = True
            continue
        # Avoid near-duplicates like "Mold Design Stream"
        matched = next(
            (
                stream
                for existing_key, stream in existing.items()
                if key in existing_key or existing_key in key
            ),
            None,
        )
        if matched is not None:
            existing[key] = matched
            continue
        stream = Stream(name=name, description=description, is_active=True)
        db.add(stream)
        existing[key] = stream
        created += 1
    if created:
        db.flush()
    return created
