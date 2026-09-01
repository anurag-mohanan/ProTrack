"""Selectable sections for designer/team timesheet Excel exports."""

from __future__ import annotations

from fastapi import HTTPException, status

TIMESHEET_SECTION_DESIGNERS = "designers"
TIMESHEET_SECTION_PROJECTS = "projects"
TIMESHEET_SECTION_CROSS_TEAM = "cross_team"
TIMESHEET_SECTION_UTILIZATION = "utilization"

TIMESHEET_REPORT_SECTIONS: dict[str, str] = {
    TIMESHEET_SECTION_DESIGNERS: "Designer Hours by Team",
    TIMESHEET_SECTION_PROJECTS: "Project Hours",
    TIMESHEET_SECTION_CROSS_TEAM: "Cross-Team Hours",
    TIMESHEET_SECTION_UTILIZATION: "Utilization Summary",
}

TIMESHEET_SECTION_DESCRIPTIONS: dict[str, str] = {
    TIMESHEET_SECTION_DESIGNERS: (
        "Summary of hours recorded by each designer within the selected team and period."
    ),
    TIMESHEET_SECTION_PROJECTS: (
        "Hours recorded against each project during the selected reporting period."
    ),
    TIMESHEET_SECTION_CROSS_TEAM: (
        "Hours logged on another team's projects (outbound/inbound) during the period."
    ),
    TIMESHEET_SECTION_UTILIZATION: (
        "Utilization based on productive hours and applicable working days from team assignment."
    ),
}

DEFAULT_TIMESHEET_SECTIONS: tuple[str, ...] = tuple(TIMESHEET_REPORT_SECTIONS.keys())

_SECTION_ORDER: tuple[str, ...] = DEFAULT_TIMESHEET_SECTIONS
SECTION_ORDER: tuple[str, ...] = _SECTION_ORDER


def parse_timesheet_sections(raw: str | None) -> list[str]:
    """Parse comma-separated section ids; default is all sections."""
    if raw is None or not str(raw).strip():
        return list(DEFAULT_TIMESHEET_SECTIONS)
    tokens = [part.strip().lower() for part in str(raw).split(",") if part.strip()]
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one report section.",
        )
    unknown = [token for token in tokens if token not in TIMESHEET_REPORT_SECTIONS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown report section(s): {', '.join(unknown)}",
        )
    ordered = [section for section in _SECTION_ORDER if section in tokens]
    if not ordered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one report section.",
        )
    return ordered


def normalize_timesheet_sections(sections: list[str] | None) -> list[str]:
    if sections is None or len(sections) == 0:
        return list(DEFAULT_TIMESHEET_SECTIONS)
    tokens = [str(s).strip().lower() for s in sections if str(s).strip()]
    unknown = [token for token in tokens if token not in TIMESHEET_REPORT_SECTIONS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown report section(s): {', '.join(unknown)}",
        )
    ordered = [section for section in _SECTION_ORDER if section in tokens]
    if not ordered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select at least one report section.",
        )
    return ordered
