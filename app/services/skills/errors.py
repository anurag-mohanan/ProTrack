"""Skill service errors, mapped to HTTP status codes by the API layer."""

from __future__ import annotations


class SkillError(Exception):
    status_code = 400

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class SkillValidationError(SkillError):
    status_code = 400


class SkillConflictError(SkillError):
    status_code = 409


class SkillPermissionError(SkillError):
    status_code = 403


class SkillNotFoundError(SkillError):
    status_code = 404
