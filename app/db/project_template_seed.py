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

MilestoneDef = tuple[str, str | None, int | None, bool]

TEMPLATE_DEFINITIONS: list[dict] = [
    {
        "name": "General Mold Design",
        "project_type": "Mold Design",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Feasibility", None, 7, True),
            ("Blockout", None, 14, True),
            ("Roughing", None, 21, True),
            ("Intermediate Review", None, 28, True),
            ("Final Review", None, 35, True),
            ("File Release", None, 42, True),
            ("BOM Release", None, 49, True),
        ],
    },
    {
        "name": "Sybridge Mold Design",
        "project_type": "Mold Design",
        "customer": "Sybridge",
        "is_default": False,
        "milestones": [
            ("Feasibility", None, 7, True),
            ("Blockout", None, 14, True),
            ("Customer Intermediate Review", None, 21, True),
            ("Final Review", None, 28, True),
            ("File Release", None, 35, True),
            ("BOM Release", None, 42, True),
        ],
    },
    {
        "name": "Lamko Mold Design",
        "project_type": "Mold Design",
        "customer": "Lamko",
        "is_default": False,
        "milestones": [
            ("Concept Review", None, 7, True),
            ("Blockout", None, 14, True),
            ("Design Review", None, 21, True),
            ("Tool Review", None, 28, True),
            ("Release", None, 35, True),
        ],
    },
    {
        "name": "TI Automotive Mold Design",
        "project_type": "Mold Design",
        "customer": "TI Automotive",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True),
            ("GT1", None, 14, True),
            ("Roughing", None, 21, True),
            ("GT2", None, 28, True),
            ("Intermediate", None, 35, True),
            ("GT3", None, 42, True),
            ("EOI 4", None, 49, True),
            ("EOI 5", None, 56, True),
            ("EOI 6", None, 63, True),
            ("Final", None, 70, True),
            ("GT4", None, 77, True),
            ("Plaques", None, 84, True),
        ],
    },
    {
        "name": "Crest Mold Technologies Mold Design",
        "project_type": "Mold Design",
        "customer": "Crest Mold Technologies (CMT)",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True),
            ("Roughing", None, 14, True),
            ("Intermediate", None, 21, True),
            ("Engraving Proposal", None, 28, True),
            ("Final", None, 35, True),
            ("Files Released", None, 42, True),
            ("BOM", None, 49, True),
            ("Plaques", None, 56, True),
        ],
    },
    {
        "name": "B & B Tool & Mould Mold Design",
        "project_type": "Mold Design",
        "customer": "B & B Tool & Mould",
        "is_default": False,
        "milestones": [
            ("Blockout", None, 7, True),
            ("Roughing", None, 14, True),
            ("Intermediate", None, 21, True),
            ("Engraving Proposal", None, 28, True),
            ("Final", None, 35, True),
            ("Files Released", None, 42, True),
            ("BOM", None, 49, True),
            ("Plaques", None, 56, True),
        ],
    },
    {
        "name": "Engineering Change",
        "project_type": "Engineering Change",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Review EC", None, 3, True),
            ("Update CAD", None, 7, True),
            ("Internal Review", None, 10, True),
            ("Customer Approval", None, 14, True),
            ("File Release", None, 17, True),
        ],
    },
    {
        "name": "DFM Only",
        "project_type": "DFM",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Import CAD", None, 3, True),
            ("Draft DFM", None, 7, True),
            ("Internal Review", None, 10, True),
            ("Customer Review", None, 14, True),
            ("Final DFM", None, 17, True),
        ],
    },
    {
        "name": "Surfacing Only",
        "project_type": "Surfacing",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Surface Import", None, 3, True),
            ("Surface Creation", None, 7, True),
            ("Surface Validation", None, 10, True),
            ("Customer Review", None, 14, True),
            ("Final Surface Release", None, 17, True),
        ],
    },
    {
        "name": "Fixture Design",
        "project_type": "Fixture",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Concept", None, 5, True),
            ("Design", None, 10, True),
            ("Internal Review", None, 14, True),
            ("Customer Review", None, 18, True),
            ("Drawing Release", None, 21, True),
        ],
    },
    {
        "name": "Electrode Design",
        "project_type": "Electrode",
        "customer": None,
        "is_default": True,
        "milestones": [
            ("Concept", None, 5, True),
            ("Design", None, 10, True),
            ("Internal Review", None, 14, True),
            ("Customer Review", None, 18, True),
            ("Drawing Release", None, 21, True),
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
    for sort_order, (name, description, offset_days, is_required) in enumerate(
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
            )
        )


def ensure_project_types_and_templates(session: Session) -> None:
    for name, code in CUSTOMER_SEED:
        _get_or_create_customer(session, name, code)

    type_by_name: dict[str, ProjectType] = {}
    for name in PROJECT_TYPE_NAMES:
        type_by_name[name] = _get_or_create_project_type(session, name)

    for definition in TEMPLATE_DEFINITIONS:
        project_type = type_by_name[definition["project_type"]]
        customer = None
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

    session.commit()
