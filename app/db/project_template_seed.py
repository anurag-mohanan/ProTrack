"""Seed project types and default milestone templates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.models import Customer, ProjectTemplate, ProjectTemplateMilestone, ProjectType

logger = logging.getLogger(__name__)

PROJECT_TYPE_NAMES = (
    "Mold Design",
    "CAD Development",
    "Engineering Change",
    "DFM",
    "Surfacing",
    "Fixture",
    "Electrode",
    "CAD Support",
    "Tooling Support",
)

# (name, description, due_offset_days, is_required, assigned_role)
MilestoneDef = tuple[str, str | None, int | None, bool, str | None]

TEMPLATE_DEFINITIONS: list[dict] = [
    {
        "name": "General Mold Design",
        "project_type": "Mold Design",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Feasibility", None, 7, True, "Surfacer"),
            ("Blockout", None, 14, True, "Designer"),
            ("Roughing", None, 21, True, "Designer"),
            ("Intermediate Review", None, 28, True, "Designer"),
            ("Final Review", None, 35, True, "Designer"),
            ("File Release", None, 42, True, "Designer"),
            ("BOM Release", None, 49, True, "Designer"),
        ],
    },
    {
        "name": "CAD Development",
        "project_type": "CAD Development",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Requirements Review", None, 7, True, "Designer"),
            ("Reference Data Collection", None, 14, True, "Designer"),
            ("Library Folder Structure Created", None, 21, True, "Designer"),
            ("Base Template Created", None, 28, True, "Designer"),
            ("3D Component Modeling Complete", None, 35, True, "Designer"),
            ("Component Attributes Added", None, 42, True, "Designer"),
            ("Material and Metadata Assigned", None, 49, True, "Designer"),
            ("Preview Icons Generated", None, 56, True, "Designer"),
            ("Assembly Integration Tested", None, 63, True, "Designer"),
            ("Documentation Completed", None, 70, True, "Designer"),
            ("User Acceptance Testing (UAT)", None, 77, True, "Designer"),
            ("Library Packaging Completed", None, 84, True, "Designer"),
            ("Production Library Release", None, 91, True, "Designer"),
            ("Version & Revision Published", None, 98, True, "Designer"),
            ("Lessons Learned / Project Closure", None, 105, True, "Designer"),
        ],
    },
    {
        "name": "Sybridge Mold Design",
        "project_type": "Mold Design",
        "customer": "Sybridge",
        "is_default": False,
        "milestones": [
            ("Feasibility", None, 7, True, "Surfacer"),
            ("Blockout", None, 14, True, "Designer"),
            ("Customer Intermediate Review", None, 21, True, "Designer"),
            ("Final Review", None, 28, True, "Designer"),
            ("File Release", None, 35, True, "Designer"),
            ("BOM Release", None, 42, True, "Designer"),
        ],
    },
    {
        "name": "Lamko Mold Design",
        "project_type": "Mold Design",
        "customer": "Lamko",
        "is_default": False,
        "milestones": [
            ("Concept Review", None, 7, True, "Designer"),
            ("Blockout", None, 14, True, "Designer"),
            ("Design Review", None, 21, True, "Designer"),
            ("Tool Review", None, 28, True, "Designer"),
            ("Release", None, 35, True, "Designer"),
        ],
    },
    {
        "name": "TI Automotive Template",
        "project_type": "Mold Design",
        "customer": "TI Automotive",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True, "Designer"),
            ("GT1", None, 14, True, "Designer"),
            ("Roughing", None, 21, True, "Designer"),
            ("GT2", None, 28, True, "Designer"),
            ("Intermediate", None, 35, True, "Designer"),
            ("GT3", None, 42, True, "Designer"),
            ("EOI 4", None, 49, True, "Designer"),
            ("EOI 5", None, 56, True, "Designer"),
            ("EOI 6", None, 63, True, "Designer"),
            ("Final", None, 70, True, "Designer"),
            ("GT4", None, 77, True, "Designer"),
            ("Plaques", None, 84, True, "Designer"),
        ],
    },
    {
        "name": "Crest Mold Technologies Template",
        "project_type": "Mold Design",
        "customer": "Crest Mold Technologies (CMT)",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True, "Designer"),
            ("Roughing", None, 14, True, "Designer"),
            ("Intermediate", None, 21, True, "Designer"),
            ("Engraving Proposal", None, 28, True, "Designer"),
            ("Final", None, 35, True, "Designer"),
            ("Files Released", None, 42, True, "Designer"),
            ("BOM", None, 49, True, "Designer"),
            ("Plaques", None, 56, True, "Designer"),
        ],
    },
    {
        "name": "B & B Tool & Mould Template",
        "project_type": "Mold Design",
        "customer": "B & B Tool & Mould",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True, "Designer"),
            ("Roughing", None, 14, True, "Designer"),
            ("Intermediate", None, 21, True, "Designer"),
            ("Engraving Proposal", None, 28, True, "Designer"),
            ("Final", None, 35, True, "Designer"),
            ("Files Released", None, 42, True, "Designer"),
            ("BOM", None, 49, True, "Designer"),
            ("Plaques", None, 56, True, "Designer"),
        ],
    },
    {
        "name": "Engineering Change",
        "project_type": "Engineering Change",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Review EC", None, 3, True, "Designer"),
            ("Update CAD", None, 7, True, "Designer"),
            ("Internal Review", None, 10, True, "Designer"),
            ("Customer Approval", None, 14, True, "Designer"),
            ("File Release", None, 17, True, "Designer"),
        ],
    },
    {
        "name": "DFM Only",
        "project_type": "DFM",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Import CAD", None, 3, True, "Designer"),
            ("Draft DFM", None, 7, True, "Designer"),
            ("Internal Review", None, 10, True, "Designer"),
            ("Customer Review", None, 14, True, "Designer"),
            ("Final DFM", None, 17, True, "Designer"),
        ],
    },
    {
        "name": "Surfacing Only",
        "project_type": "Surfacing",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Surface Import", None, 3, True, "Surfacer"),
            ("Surface Creation", None, 7, True, "Surfacer"),
            ("Surface Validation", None, 10, True, "Surfacer"),
            ("Customer Review", None, 14, True, "Surfacer"),
            ("Final Surface Release", None, 17, True, "Surfacer"),
        ],
    },
    {
        "name": "Fixture Design",
        "project_type": "Fixture",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Concept", None, 5, True, "Designer"),
            ("Design", None, 10, True, "Designer"),
            ("Internal Review", None, 14, True, "Designer"),
            ("Customer Review", None, 18, True, "Designer"),
            ("Drawing Release", None, 21, True, "Designer"),
        ],
    },
    {
        "name": "Electrode Design",
        "project_type": "Electrode",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Concept", None, 5, True, "Designer"),
            ("Design", None, 10, True, "Designer"),
            ("Internal Review", None, 14, True, "Designer"),
            ("Customer Review", None, 18, True, "Designer"),
            ("Drawing Release", None, 21, True, "Designer"),
        ],
    },
]

CUSTOMER_SEED = (
    ("Sybridge", "SYB"),
    ("Lamko", "LAM"),
    ("TI Automotive", "TIAT"),
    ("Crest Mold Technologies (CMT)", "CMTC"),
    ("B & B Tool & Mould", "BBTM"),
)

CUSTOMER_DEFAULT_TEMPLATES: dict[str, str] = {
    "Sybridge": "Sybridge Mold Design",
    "Lamko": "Lamko Mold Design",
    "TI Automotive": "TI Automotive Template",
    "Crest Mold Technologies (CMT)": "Crest Mold Technologies Template",
    "B & B Tool & Mould": "B & B Tool & Mould Template",
}

LEGACY_TEMPLATE_NAMES: dict[str, str] = {
    "TI Automotive Mold Design": "TI Automotive Template",
    "Crest Mold Technologies Mold Design": "Crest Mold Technologies Template",
    "B & B Tool & Mould Mold Design": "B & B Tool & Mould Template",
}


def _get_or_create_customer(session: Session, name: str, code: str) -> Customer:
    customer = session.scalar(select(Customer).where(Customer.name == name))
    if customer is not None:
        return customer
    customer = Customer(name=name, code=code, is_active=True)
    session.add(customer)
    session.flush()
    return customer


def _get_or_create_project_type(session: Session, name: str) -> ProjectType:
    project_type = session.scalar(select(ProjectType).where(ProjectType.name == name))
    if project_type is not None:
        return project_type
    project_type = ProjectType(name=name, is_active=True)
    session.add(project_type)
    session.flush()
    return project_type


def _add_milestones(
    session: Session,
    template: ProjectTemplate,
    milestones: list[MilestoneDef],
) -> None:
    for sort_order, (name, description, offset_days, is_required, assigned_role) in enumerate(
        milestones, start=1
    ):
        session.add(
            ProjectTemplateMilestone(
                project_template_id=template.id,
                milestone_name=name,
                description=description,
                sort_order=sort_order,
                default_due_offset_days=offset_days,
                is_required=is_required,
                is_visible=True,
                assigned_role=assigned_role,
            )
        )


def _expected_milestone_names(milestones: list[MilestoneDef]) -> list[str]:
    return [name for name, *_rest in milestones]


def _sync_template_milestones(
    session: Session,
    template: ProjectTemplate,
    milestones: list[MilestoneDef],
) -> None:
    existing_names = [
        milestone.milestone_name
        for milestone in sorted(template.milestones, key=lambda item: item.sort_order)
    ]
    if existing_names == _expected_milestone_names(milestones):
        return
    for existing in list(template.milestones):
        session.delete(existing)
    session.flush()
    _add_milestones(session, template, milestones)


def _rename_legacy_templates(session: Session) -> None:
    for old_name, new_name in LEGACY_TEMPLATE_NAMES.items():
        legacy = session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == old_name))
        if legacy is None:
            continue
        conflict = session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == new_name))
        if conflict is None:
            legacy.name = new_name
            session.add(legacy)


def _link_customer_defaults(session: Session, type_by_name: dict[str, ProjectType]) -> None:
    mold_type = type_by_name.get("Mold Design")
    for customer_name, template_name in CUSTOMER_DEFAULT_TEMPLATES.items():
        customer = session.scalar(select(Customer).where(Customer.name == customer_name))
        template = session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == template_name))
        if customer is None or template is None:
            continue
        customer.default_project_template_id = template.id
        if mold_type is not None and customer.default_project_type_id is None:
            customer.default_project_type_id = mold_type.id
        session.add(customer)


def ensure_project_types_and_templates(session: Session) -> None:
    for name, code in CUSTOMER_SEED:
        _get_or_create_customer(session, name, code)

    type_by_name: dict[str, ProjectType] = {}
    for name in PROJECT_TYPE_NAMES:
        type_by_name[name] = _get_or_create_project_type(session, name)

    _rename_legacy_templates(session)

    for definition in TEMPLATE_DEFINITIONS:
        project_type = type_by_name[definition["project_type"]]
        customer_id = None
        if definition["customer"]:
            customer = session.scalar(
                select(Customer).where(Customer.name == definition["customer"])
            )
            customer_id = customer.id if customer else None

        existing = session.scalar(
            select(ProjectTemplate)
            .options(selectinload(ProjectTemplate.milestones))
            .where(ProjectTemplate.name == definition["name"])
        )
        if existing is not None:
            if customer_id is not None and existing.customer_id != customer_id:
                existing.customer_id = customer_id
                session.add(existing)
            _sync_template_milestones(session, existing, definition["milestones"])
            continue

        template = ProjectTemplate(
            name=definition["name"],
            description=f"{definition['name']} workflow template",
            project_type_id=project_type.id,
            customer_id=customer_id,
            is_default=definition["is_default"],
            is_active=True,
        )
        session.add(template)
        session.flush()
        _add_milestones(session, template, definition["milestones"])

    _link_customer_defaults(session, type_by_name)
    session.commit()


def validate_project_template_health(session: Session) -> list[str]:
    """Return warnings when required templates, milestones, or customer links are missing."""
    warnings: list[str] = []

    template_count = session.scalar(select(func.count()).select_from(ProjectTemplate)) or 0
    if template_count == 0:
        warnings.append("No project templates found in the database.")

    milestone_count = session.scalar(select(func.count()).select_from(ProjectTemplateMilestone)) or 0
    if milestone_count == 0:
        warnings.append("No project template milestones found in the database.")

    for definition in TEMPLATE_DEFINITIONS:
        template = session.scalar(
            select(ProjectTemplate)
            .options(selectinload(ProjectTemplate.milestones))
            .where(ProjectTemplate.name == definition["name"])
        )
        if template is None:
            warnings.append(f"Missing template: {definition['name']}")
            continue
        if not template.is_active:
            warnings.append(f"Template inactive: {definition['name']}")
        expected = _expected_milestone_names(definition["milestones"])
        actual = [
            milestone.milestone_name
            for milestone in sorted(template.milestones, key=lambda item: item.sort_order)
        ]
        if actual != expected:
            warnings.append(
                f"Template milestone mismatch for {definition['name']}: "
                f"expected {len(expected)}, found {len(actual)}"
            )

    for customer_name, template_name in CUSTOMER_DEFAULT_TEMPLATES.items():
        customer = session.scalar(select(Customer).where(Customer.name == customer_name))
        template = session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == template_name))
        if customer is None:
            warnings.append(f"Missing customer for default template mapping: {customer_name}")
            continue
        if template is None:
            warnings.append(f"Missing template for customer mapping: {template_name}")
            continue
        if customer.default_project_template_id != template.id:
            warnings.append(
                f"Customer default template not linked: {customer_name} -> {template_name}"
            )

    for warning in warnings:
        logger.warning("Project template health check: %s", warning)

    return warnings


def export_project_templates_to_json(
    session: Session,
    output_path: str | Path,
) -> dict[str, Any]:
    """Export all templates (with milestones) to a JSON seed file for disaster recovery."""
    templates = session.scalars(
        select(ProjectTemplate)
        .options(selectinload(ProjectTemplate.milestones))
        .order_by(ProjectTemplate.name.asc())
    ).all()

    payload: dict[str, Any] = {
        "exported_template_count": len(templates),
        "templates": [],
    }

    for template in templates:
        customer_name = None
        if template.customer_id is not None:
            customer = session.get(Customer, template.customer_id)
            customer_name = customer.name if customer else None
        project_type = session.get(ProjectType, template.project_type_id)
        milestones = sorted(template.milestones, key=lambda item: item.sort_order)
        payload["templates"].append(
            {
                "name": template.name,
                "description": template.description,
                "project_type": project_type.name if project_type else None,
                "customer": customer_name,
                "is_default": template.is_default,
                "is_active": template.is_active,
                "milestones": [
                    {
                        "milestone_name": milestone.milestone_name,
                        "description": milestone.description,
                        "sort_order": milestone.sort_order,
                        "default_due_offset_days": milestone.default_due_offset_days,
                        "is_required": milestone.is_required,
                        "is_visible": milestone.is_visible,
                        "project_stage": milestone.project_stage,
                        "estimated_hours": milestone.estimated_hours,
                        "assigned_role": milestone.assigned_role,
                        "default_assigned_user_id": (
                            str(milestone.default_assigned_user_id)
                            if milestone.default_assigned_user_id
                            else None
                        ),
                    }
                    for milestone in milestones
                ],
            }
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
