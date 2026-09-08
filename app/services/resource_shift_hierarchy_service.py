"""Shift → team → employee → computer → IP → software → project tree.

Read-only aggregate for Resource Planning. Does not invent assignments.
Unassigned employees remain visible in an Unassigned bucket.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus
from app.models.it_operations import (
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareInstallation,
    SoftwareLicensePool,
)
from app.models.models import Project, Team, TeamMember, User
from app.models.resource_shifts import ResourceShift
from app.services import resource_shift_service as shift_service
from app.services.it_network_service import list_ips_for_user
from app.services.resource_it_gap_service import (
    _computer_assignment_map,
    _full_name,
    get_software_requirements,
)


def _active_users(db: Session, team_id: UUID | None) -> list[User]:
    stmt = select(User).where(
        User.is_deleted.is_(False),
        User.is_active.is_(True),
        User.is_archived.is_(False),
    )
    users = list(db.scalars(stmt).all())
    if team_id is None:
        return users
    member_ids = set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )
    return [row for row in users if row.id in member_ids]


def _primary_team_by_user(db: Session, user_ids: list[UUID]) -> dict[UUID, tuple[UUID, str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(TeamMember, Team)
        .join(Team, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id.in_(user_ids))
        .order_by(TeamMember.is_primary.desc(), Team.name)
    ).all()
    mapping: dict[UUID, tuple[UUID, str]] = {}
    for member, team in rows:
        if member.user_id not in mapping or member.is_primary:
            mapping[member.user_id] = (team.id, team.name)
    return mapping


def _projects_by_user(db: Session, user_ids: list[UUID]) -> dict[UUID, list[dict]]:
    if not user_ids:
        return {}
    rows = db.scalars(
        select(Project).where(
            Project.is_deleted.is_(False),
            Project.execution_status.notin_(
                (ExecutionStatus.completed, ExecutionStatus.cancelled)
            ),
            or_(
                Project.designer_id.in_(user_ids),
                Project.design_leader_id.in_(user_ids),
                Project.surfacer_id.in_(user_ids),
            ),
        )
    ).all()
    by_user: dict[UUID, list[dict]] = defaultdict(list)
    seen: dict[UUID, set[UUID]] = defaultdict(set)
    for project in rows:
        payload = {
            "id": str(project.id),
            "tool_number": project.tool_number,
            "name": project.part_description,
        }
        for uid in (project.designer_id, project.design_leader_id, project.surfacer_id):
            if uid is None or uid not in user_ids:
                continue
            if project.id in seen[uid]:
                continue
            seen[uid].add(project.id)
            by_user[uid].append(payload)
    return by_user


def _licensed_names_by_user(db: Session, user_ids: list[UUID]) -> dict[UUID, list[str]]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(SoftwareAssignment.user_id, SoftwareCatalog.name)
        .join(
            SoftwareLicensePool,
            SoftwareLicensePool.id == SoftwareAssignment.license_pool_id,
        )
        .join(SoftwareCatalog, SoftwareCatalog.id == SoftwareLicensePool.software_id)
        .where(
            SoftwareAssignment.user_id.in_(user_ids),
            SoftwareAssignment.released_date.is_(None),
        )
        .order_by(SoftwareCatalog.name)
    ).all()
    mapping: dict[UUID, list[str]] = defaultdict(list)
    for user_id, name in rows:
        if name:
            mapping[user_id].append(name)
    return mapping


def _installed_names_by_computer(db: Session, computer_ids: list[UUID]) -> dict[UUID, list[str]]:
    if not computer_ids:
        return {}
    rows = db.execute(
        select(SoftwareInstallation.computer_id, SoftwareCatalog.name)
        .join(SoftwareCatalog, SoftwareCatalog.id == SoftwareInstallation.software_id)
        .where(
            SoftwareInstallation.computer_id.in_(computer_ids),
            SoftwareInstallation.uninstalled_date.is_(None),
        )
        .order_by(SoftwareCatalog.name)
    ).all()
    mapping: dict[UUID, list[str]] = defaultdict(list)
    for computer_id, name in rows:
        if name:
            mapping[computer_id].append(name)
    return mapping


def build_shift_hierarchy(
    db: Session,
    *,
    on_date: date | None = None,
    team_id: UUID | None = None,
) -> dict:
    day = on_date or date.today()
    users = _active_users(db, team_id)
    user_ids = [row.id for row in users]
    shifts = list(
        db.scalars(
            select(ResourceShift)
            .where(ResourceShift.is_active.is_(True))
            .order_by(ResourceShift.start_time, ResourceShift.name)
        ).all()
    )
    resolved = shift_service.resolve_shifts_for_range(db, user_ids, day, day) if user_ids else {}
    teams = _primary_team_by_user(db, user_ids)
    computers = _computer_assignment_map(db, day)
    computer_ids = [
        row["computer_id"] for row in computers.values() if row.get("computer_id")
    ]
    installed = _installed_names_by_computer(db, computer_ids)
    licensed = _licensed_names_by_user(db, user_ids)
    requirements = get_software_requirements(db, user_ids, on_date=day) if user_ids else {}
    projects = _projects_by_user(db, user_ids)

    people_payload: list[dict] = []
    for user in users:
        shift = (resolved.get(user.id) or {}).get(day)
        team = teams.get(user.id)
        computer = computers.get(user.id)
        req_names = [
            row["software_name"]
            for row in requirements.get(user.id, [])
            if row.get("requirement_level") == "required"
        ]
        missing = [
            name
            for name in req_names
            if name not in set(licensed.get(user.id, []))
        ]
        ip_rows = list_ips_for_user(db, user.id)
        cid = computer["computer_id"] if computer else None
        computer_payload = None
        if computer:
            assigned = computer.get("assigned_date")
            computer_payload = {
                "computer_id": str(computer["computer_id"]),
                "computer_name": computer.get("computer_name"),
                "asset_id": str(computer["asset_id"]) if computer.get("asset_id") else None,
                "asset_number": computer.get("asset_number"),
                "asset_status": computer.get("asset_status"),
                "assigned_date": assigned.isoformat() if assigned else None,
            }
        people_payload.append(
            {
                "user_id": str(user.id),
                "name": _full_name(user),
                "shift_id": str(shift.id) if shift is not None else None,
                "team_id": str(team[0]) if team else None,
                "team_name": team[1] if team else "No team",
                "computer": computer_payload,
                "ips": [{"id": str(ip.id), "address": ip.address} for ip in ip_rows],
                "software": licensed.get(user.id, []),
                "installed": installed.get(cid, []) if cid else [],
                "missing_software": missing,
                "projects": projects.get(user.id, []),
                "has_shortage": bool(missing) or computer is None,
            }
        )

    unassigned_key = "unassigned"
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for person in people_payload:
        shift_key = person["shift_id"] or unassigned_key
        team_key = person["team_id"] or "no-team"
        grouped[shift_key][team_key].append(person)

    tree = []
    for shift in shifts:
        team_map = grouped.get(str(shift.id), {})
        team_nodes = []
        people_count = 0
        shortage_count = 0
        for team_id_key, members in sorted(
            team_map.items(),
            key=lambda item: (item[1][0]["team_name"] if item[1] else ""),
        ):
            people_count += len(members)
            shortage_count += sum(1 for row in members if row["has_shortage"])
            team_nodes.append(
                {
                    "id": team_id_key,
                    "name": members[0]["team_name"] if members else "No team",
                    "people_count": len(members),
                    "shortage_count": sum(1 for row in members if row["has_shortage"]),
                    "people": sorted(members, key=lambda row: row["name"]),
                }
            )
        tree.append(
            {
                "id": str(shift.id),
                "name": shift.name,
                "code": shift.code,
                "start_time": str(shift.start_time) if shift.start_time else None,
                "end_time": str(shift.end_time) if shift.end_time else None,
                "people_count": people_count,
                "shortage_count": shortage_count,
                "teams": team_nodes,
            }
        )

    unassigned_people = [
        person for person in people_payload if person["shift_id"] is None
    ]
    return {
        "on_date": day.isoformat(),
        "shifts": tree,
        "unassigned": {
            "people_count": len(unassigned_people),
            "shortage_count": sum(1 for row in unassigned_people if row["has_shortage"]),
            "people": sorted(unassigned_people, key=lambda row: row["name"]),
        },
        "totals": {
            "employees": len(people_payload),
            "with_computer": sum(1 for row in people_payload if row["computer"]),
            "without_computer": sum(1 for row in people_payload if not row["computer"]),
            "with_shortage": sum(1 for row in people_payload if row["has_shortage"]),
            "unassigned_shift": len(unassigned_people),
        },
    }
