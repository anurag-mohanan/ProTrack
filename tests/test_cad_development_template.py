"""CAD Development project type/template seed."""

from sqlalchemy import select

from app.db.project_template_seed import ensure_project_types_and_templates
from app.models.models import ProjectTemplate, ProjectType


def test_cad_development_template_milestones(session):
    ensure_project_types_and_templates(session)

    project_type = session.scalar(
        select(ProjectType).where(ProjectType.name == "CAD Development")
    )
    assert project_type is not None

    template = session.scalar(
        select(ProjectTemplate).where(ProjectTemplate.name == "CAD Development")
    )
    assert template is not None
    assert template.project_type_id == project_type.id
    assert template.is_default is True

    names = [row.milestone_name for row in sorted(template.milestones, key=lambda m: m.sort_order)]
    assert names == [
        "Requirements Review",
        "Reference Data Collection",
        "Library Folder Structure Created",
        "Base Template Created",
        "3D Component Modeling Complete",
        "Component Attributes Added",
        "Material and Metadata Assigned",
        "Preview Icons Generated",
        "Assembly Integration Tested",
        "Documentation Completed",
        "User Acceptance Testing (UAT)",
        "Library Packaging Completed",
        "Production Library Release",
        "Version & Revision Published",
        "Lessons Learned / Project Closure",
    ]
