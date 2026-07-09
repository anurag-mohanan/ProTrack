"""Seed project types and default milestone templates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Customer, ProjectTemplate, ProjectTemplateMilestone, ProjectType

PROJECT_TYPE_NAMES = (
    "Mold Design",
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
            select(ProjectTemplate).where(ProjectTemplate.name == definition["name"])
        )
        if existing is not None:
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
