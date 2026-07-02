from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.field_normalization import (
    annotation_allows_none,
    normalize_optional_text,
    normalize_optional_uuid,
)


class TimestampSchema(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlankOptionalFieldsMixin:
    """Coerce blank and spreadsheet error values to NULL on optional fields."""

    @model_validator(mode="before")
    @classmethod
    def normalize_blank_optional_values(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        fields = cls.model_fields
        result = dict(data)
        for name, field in fields.items():
            if name not in result:
                continue
            value = result[name]
            allows_none = annotation_allows_none(field.annotation)

            if isinstance(value, str) or value is None:
                cleaned = normalize_optional_text(value)
                if allows_none:
                    result[name] = cleaned
                elif cleaned is not None:
                    result[name] = cleaned
                continue

            if allows_none and value == "":
                result[name] = None
            elif allows_none and isinstance(value, float) and value != value:
                result[name] = None
            elif allows_none and name.endswith("_id"):
                result[name] = normalize_optional_uuid(value)

        return result
