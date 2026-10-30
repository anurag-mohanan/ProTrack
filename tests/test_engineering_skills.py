"""Phase 4: engineering skills taxonomy, verified profiles, matrix, gaps, plans, matching and capability findings."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.db.phase7_schema_sync import ensure_phase7_foundation
from app.db.phase109_engineering_skills_schema_sync import (
    ensure_phase109_engineering_skills_foundation,
)
from app.models.enums import (
    ActivityAction,
    SkillLevel,
    TeamRelationshipType,
    TimesheetStatus,
    UserAvailabilityStatus,
)
from app.models.foundation import Skill, UserSkill
from app.models.models import Activity, Project, Team, TeamMember, User
from app.models.skills import ProjectSkillRequirement, UserSkillEvent
from app.services.control_tower_service import detect_all, rule_catalog
from tests.conftest import IDS, login
from tests.test_engineering_metrics import _book, _project

API = "/api/v1/skills"


def _h(client, who: str) -> dict:
    if who == "admin":
        return client.auth_headers
    tokens = client.__dict__.setdefault("_skill_tokens", {})
    if who not in tokens:
        tokens[who] = login(client, f"{who}@prosohm.com")
    return tokens[who]


def _ok(response, code: int = 200):
    assert response.status_code == code, response.text
    return response.json() if response.content else None


def _teams(session: Session) -> dict:
    """Team A (lead: Anurag) holds Binil and Logesh; team B holds Ranjith with no lead from team A."""
    team_a = Team(id=uuid.uuid4(), name="Skills Mold A", team_lead_id=IDS["user_anurag"], is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Skills Surface B", is_active=True)
    session.add_all([team_a, team_b])
    session.flush()
    logesh = session.scalar(select(User).where(User.email == "logesh@prosohm.com"))
    for team, user_id in ((team_a, IDS["user_binil"]), (team_a, logesh.id), (team_b, IDS["user_ranjith"])):
        session.add(TeamMember(team_id=team.id, user_id=user_id, relationship_type=TeamRelationshipType.member))
    session.commit()
    return {"a": team_a.id, "b": team_b.id, "logesh": logesh.id}


def _skill(client, name: str, **extra) -> str:
    body = {"name": name, "category": extra.pop("category", "Mold design engineering"), **extra}
    return _ok(client.post(f"{API}/taxonomy/skills", json=body, headers=client.auth_headers), 201)["id"]


def _nx_id(session: Session) -> str:
    return str(session.scalar(select(Skill.id).where(Skill.name == "NX")))


def _declare(client, who: str, skill_id: str, level: int, submit: bool = False):
    return _ok(
        client.post(
            f"{API}/me/declarations",
            json={"skill_id": skill_id, "declared_level": level, "submit_for_verification": submit},
            headers=_h(client, who),
        )
    )


def _assess(client, who: str, subject_id, skill_id: str, decision: str, level: int | None = None, code: int = 200, **extra):
    body = {"skill_id": skill_id, "decision": decision, "level": level, **extra}
    response = client.post(f"{API}/profiles/{subject_id}/assess", json=body, headers=_h(client, who))
    assert response.status_code == code, response.text
    return response.json()


def _record(profile: dict, skill_id: str) -> dict:
    return next(r for r in profile["records"] if r["skill_id"] == skill_id)


# ----------------------------------------------------------------- taxonomy


def test_taxonomy_create_dedupe_alias_rename_and_deactivate(client, session):
    hot = _skill(client, "Hot runner design", aliases=["Hot-runner"], kind="specialization")
    for duplicate in ("hot runner  DESIGN", "Hot-Runner", "hot runner", "HOT_RUNNER design"):
        response = client.post(f"{API}/taxonomy/skills", json={"name": duplicate}, headers=client.auth_headers)
        assert response.status_code == 409, (duplicate, response.text)
    _skill(client, "Hot runner balancing")
    # "Siemens NX" with alias NX collides with the existing NX skill instead of creating a second NX.
    response = client.post(f"{API}/taxonomy/skills", json={"name": "Siemens NX", "aliases": ["NX"]}, headers=client.auth_headers)
    assert response.status_code == 409 and "NX" in response.text

    renamed = {"name": "Hot runner layout", "category": "mold DESIGN engineering", "kind": "specialization", "aliases": ["Hot-runner"]}
    _ok(client.put(f"{API}/taxonomy/skills/{hot}", json=renamed, headers=client.auth_headers))
    row = session.get(Skill, uuid.UUID(hot))
    session.refresh(row)
    assert row.name == "Hot runner layout"
    assert row.category == "Mold design engineering"  # reuses the existing spelling
    assert "Hot runner design" in row.aliases  # old name kept as an alias, so it cannot be re-created
    assert client.post(f"{API}/taxonomy/skills", json={"name": "Hot Runner Design"}, headers=client.auth_headers).status_code == 409

    _ok(client.put(f"{API}/taxonomy/skills/{hot}", json={**renamed, "is_active": False}, headers=client.auth_headers))
    active = _ok(client.get(f"{API}/taxonomy", headers=_h(client, "binil")))
    assert hot not in {s["id"] for s in active["skills"]}
    everything = _ok(client.get(f"{API}/taxonomy?include_inactive=true", headers=client.auth_headers))
    assert hot in {s["id"] for s in everything["skills"]}
    assert session.get(Skill, uuid.UUID(hot)) is not None  # deactivated, never deleted

    assert _ok(client.post(f"{API}/taxonomy/categories/rename", json={"old": "cad", "new": "CAD software"}, headers=client.auth_headers))["updated"] == 5
    assert client.post(f"{API}/taxonomy/skills", json={"name": "Cimatron"}, headers=_h(client, "binil")).status_code == 403
    assert client.post(f"{API}/taxonomy/categories/rename", json={"old": "CAD software", "new": "x"}, headers=_h(client, "anurag")).status_code == 403
    changes = session.scalar(select(func.count(Activity.id)).where(Activity.action == ActivityAction.skill_taxonomy_changed))
    assert changes >= 4


def test_relationships_reject_self_duplicates_and_cycles(client):
    nx_like = _skill(client, "Cimatron", category="CAD", kind="software")
    discipline = _skill(client, "Injection mold design", kind="discipline")
    special = _skill(client, "Slider and lifter design", kind="specialization")
    _ok(client.post(f"{API}/taxonomy/relationships", json={"from_skill_id": nx_like, "to_skill_id": discipline, "relation_type": "used_with"}, headers=client.auth_headers), 201)
    _ok(client.post(f"{API}/taxonomy/relationships", json={"from_skill_id": special, "to_skill_id": discipline, "relation_type": "specialization_of"}, headers=client.auth_headers), 201)
    dup = client.post(f"{API}/taxonomy/relationships", json={"from_skill_id": special, "to_skill_id": discipline, "relation_type": "specialization_of"}, headers=client.auth_headers)
    assert dup.status_code == 409
    cycle = client.post(f"{API}/taxonomy/relationships", json={"from_skill_id": discipline, "to_skill_id": special, "relation_type": "specialization_of"}, headers=client.auth_headers)
    assert cycle.status_code == 400
    self_link = client.post(f"{API}/taxonomy/relationships", json={"from_skill_id": special, "to_skill_id": special, "relation_type": "related"}, headers=client.auth_headers)
    assert self_link.status_code == 400
    taxonomy = _ok(client.get(f"{API}/taxonomy", headers=client.auth_headers))
    assert {(r["from_skill_name"], r["relation_type"], r["to_skill_name"]) for r in taxonomy["relationships"]} == {
        ("Cimatron", "used_with", "Injection mold design"),
        ("Slider and lifter design", "specialization_of", "Injection mold design"),
    }


def test_standard_pack_is_dry_run_first_idempotent_and_reuses_existing(client, session):
    before = session.scalar(select(func.count(Skill.id)))
    preview = _ok(client.post(f"{API}/taxonomy/standard-pack?dry_run=true", headers=client.auth_headers))
    assert session.scalar(select(func.count(Skill.id))) == before
    present = {row["name"]: row["existing_name"] for row in preview["already_present"]}
    assert present["Siemens NX"] == "NX"
    loaded = _ok(client.post(f"{API}/taxonomy/standard-pack?dry_run=false", headers=client.auth_headers))
    assert len(loaded["created"]) == len(preview["created"]) > 0
    assert session.scalar(select(func.count(Skill.id))) == before + len(preview["created"])
    again = _ok(client.post(f"{API}/taxonomy/standard-pack?dry_run=false", headers=client.auth_headers))
    assert again["created"] == []
    assert session.scalar(select(func.count(Skill.id)).where(Skill.name.in_(["NX", "Siemens NX"]))) == 1
    cimatron = session.scalar(select(Skill).where(Skill.name == "Cimatron"))
    assert cimatron.category == "CAD"  # grouped with the existing CAD skills
    assert client.post(f"{API}/taxonomy/standard-pack?dry_run=false", headers=_h(client, "pm")).status_code == 403


def test_proficiency_framework_is_configurable(client):
    levels = _ok(client.get(f"{API}/taxonomy", headers=client.auth_headers))["proficiency_levels"]
    assert [(lvl["level"], lvl["name"]) for lvl in levels] == [
        (1, "Awareness"), (2, "Basic"), (3, "Intermediate"), (4, "Advanced"), (5, "Expert"),
    ]
    updated = _ok(client.put(f"{API}/taxonomy/levels/3", json={"name": "Competent", "description": "Works unaided on standard tools."}, headers=client.auth_headers))
    assert next(lvl for lvl in updated if lvl["level"] == 3)["name"] == "Competent"
    assert client.put(f"{API}/taxonomy/levels/6", json={"name": "Guru"}, headers=client.auth_headers).status_code == 400
    assert client.put(f"{API}/taxonomy/levels/2", json={"name": "x"}, headers=_h(client, "binil")).status_code == 403


# ----------------------------------------------------------------- profiles and verification


def test_self_declaration_is_never_verification_and_missing_is_not_level_zero(client, session):
    teams = _teams(session)
    nx = _nx_id(session)
    creo = str(session.scalar(select(Skill.id).where(Skill.name == "Creo")))
    catia = str(session.scalar(select(Skill.id).where(Skill.name == "CATIA")))
    assert _declare(client, "binil", nx, 3)["status"] == "self_declared"
    assert _declare(client, "binil", creo, 2, submit=True)["status"] == "pending_verification"

    me = _ok(client.get(f"{API}/me", headers=_h(client, "binil")))
    assert {r["skill_name"]: (r["state"], r["declared_level"], r["verified_level"]) for r in me["records"]} == {
        "NX": ("claimed", 3, None),
        "Creo": ("claimed", 2, None),
    }
    assert me["can_review"] is False and me["can_declare"] is True

    matrix = _ok(client.get(f"{API}/matrix?team_id={teams['a']}", headers=client.auth_headers))
    row = next(p for p in matrix["people"] if p["user_id"] == str(IDS["user_binil"]))
    assert row["cells"][nx]["state"] == "claimed"
    assert row["cells"][catia] == {
        "record_id": None, "state": "no_record", "verified_level": None, "declared_level": None,
        "claim_pending": False, "last_verified_at": None, "matches": True,
    }
    verified_only = _ok(client.get(f"{API}/matrix?team_id={teams['a']}&state=verified", headers=client.auth_headers))
    assert str(IDS["user_binil"]) not in {p["user_id"] for p in verified_only["people"]}
    assert client.post(f"{API}/me/declarations", json={"skill_id": nx, "declared_level": 0}, headers=_h(client, "binil")).status_code == 422


def test_verification_workflow_history_confidentiality_and_audit(client, session):
    teams = _teams(session)
    nx = _nx_id(session)
    binil = IDS["user_binil"]
    _declare(client, "binil", nx, 4, submit=True)
    queue = _ok(client.get(f"{API}/review-queue", headers=_h(client, "anurag")))
    assert [(q["skill_name"], q["reason"]) for q in queue if q["user_id"] == str(binil)] == [("NX", "Awaiting verification")]

    done = _assess(client, "anurag", binil, nx, "verify", 3, feedback="Solid core/cavity work.", confidential_note="Needs supervision on hot runners.")
    assert done["status"] == "verified" and done["verified_level"] == 3

    own = _record(_ok(client.get(f"{API}/me", headers=_h(client, "binil"))), nx)
    assert own["state"] == "verified" and own["verified_level"] == 3 and own["declared_level"] == 3
    assert own["verified_by_name"] == "Anurag Mohanan"
    assert own["assessment_feedback"] == "Solid core/cavity work."
    assert own["confidential_notes"] is None and own["confidential_hidden"] is True
    assert all(event["confidential_note"] is None for event in own["history"])
    assert [(e["action"], e["to_status"]) for e in own["history"]] == [("declared", "pending_verification"), ("verified", "verified")]
    assert own["history"][1]["detail"] == "Claimed level 4; verified at level 3."
    reviewer_view = _record(_ok(client.get(f"{API}/profiles/{binil}", headers=_h(client, "anurag"))), nx)
    assert reviewer_view["confidential_notes"] == "Needs supervision on hot runners."

    # A new claim never silently changes the verified level.
    _declare(client, "binil", nx, 5)
    session.expire_all()
    record = session.scalar(select(UserSkill).where(UserSkill.user_id == binil, UserSkill.skill_id == uuid.UUID(nx)))
    assert (record.status, record.verified_level, record.declared_level) == ("verified", 3, 5)
    queue = _ok(client.get(f"{API}/review-queue", headers=_h(client, "anurag")))
    assert [q["reason"] for q in queue if q["user_id"] == str(binil)] == ["New claim on a verified skill"]
    _assess(client, "anurag", binil, nx, "reject", feedback="Not yet at expert level.")
    session.expire_all()
    record = session.get(UserSkill, record.id)
    assert (record.status, record.verified_level, record.declared_level) == ("verified", 3, 3)

    _assess(client, "anurag", binil, nx, "request_reassessment")
    cell = next(p for p in _ok(client.get(f"{API}/matrix?team_id={teams['a']}", headers=client.auth_headers))["people"] if p["user_id"] == str(binil))["cells"][nx]
    assert cell["state"] == "reassessment"
    gap_row = next(s for s in _ok(client.get(f"{API}/gaps?team_id={teams['a']}", headers=client.auth_headers))["skills"] if s["skill_id"] == nx)
    assert gap_row["verified_count"] == 0 and gap_row["reassessment_due"] == 1

    events = session.scalars(select(UserSkillEvent).where(UserSkillEvent.user_skill_id == record.id).order_by(UserSkillEvent.occurred_at)).all()
    assert [e.action for e in events] == ["declared", "verified", "claim_updated", "rejected", "reassessment_requested"]
    activities = session.scalars(
        select(Activity).where(Activity.action == ActivityAction.skill_profile_changed, Activity.entity_id == binil)
    ).all()
    assert len(activities) == 5
    assert all("supervision" not in str(a.new_value) + str(a.old_value) for a in activities)


def test_unauthorised_reviews_and_self_assessment_are_forbidden(client, session):
    teams = _teams(session)
    nx = _nx_id(session)
    _declare(client, "ranjith", nx, 3, submit=True)
    _declare(client, "binil", nx, 3, submit=True)
    _assess(client, "logesh", IDS["user_binil"], nx, "verify", 3, code=403)  # a peer
    _assess(client, "anurag", IDS["user_ranjith"], nx, "verify", 3, code=403)  # outside Anurag's teams
    _assess(client, "anurag", IDS["user_anurag"], nx, "verify", 5, code=403)  # self
    _assess(client, "planning-board", IDS["user_binil"], nx, "verify", 3, code=403)  # shared wall-monitor login
    _assess(client, "binil", IDS["user_binil"], nx, "verify", 5, code=403)
    assert client.get(f"{API}/profiles/{IDS['user_ranjith']}", headers=_h(client, "anurag")).status_code == 403
    assert client.get(f"{API}/profiles/{IDS['user_ranjith']}", headers=_h(client, "binil")).status_code == 403
    assert client.get(f"{API}/profiles/{IDS['user_ranjith']}/experience", headers=_h(client, "binil")).status_code == 403
    assert client.get(f"{API}/matrix", headers=_h(client, "binil")).status_code == 403
    assert client.get(f"{API}/gaps", headers=_h(client, "binil")).status_code == 403
    assert client.get(f"{API}/review-queue", headers=_h(client, "binil")).status_code == 403
    assert client.get(f"{API}/matrix?team_id={teams['b']}", headers=_h(client, "anurag")).status_code == 403
    scoped = _ok(client.get(f"{API}/matrix", headers=_h(client, "anurag")))
    ids = {p["user_id"] for p in scoped["people"]}
    assert str(IDS["user_binil"]) in ids and str(IDS["user_ranjith"]) not in ids
    assert _ok(client.get(f"{API}/access", headers=_h(client, "binil"))) == {
        "can_manage_taxonomy": False, "can_view_others": False, "can_review": False, "can_match_resources": False,
    }
    # Admin (system admin) may assess anyone, but still never themselves.
    _assess(client, "admin", IDS["user_ranjith"], nx, "verify", 3)
    session.expire_all()
    assert session.scalar(select(UserSkill.status).where(UserSkill.user_id == IDS["user_ranjith"])) == "verified"


def test_archiving_and_redeclaring_never_carries_an_old_verification(client, session):
    _teams(session)
    nx = _nx_id(session)
    creo = str(session.scalar(select(Skill.id).where(Skill.name == "Creo")))
    binil = IDS["user_binil"]
    _declare(client, "binil", nx, 3, submit=True)
    _assess(client, "anurag", binil, nx, "verify", 3)
    nx_record = _record(_ok(client.get(f"{API}/me", headers=_h(client, "binil"))), nx)
    assert client.post(f"{API}/records/{nx_record['id']}/archive", json={}, headers=_h(client, "binil")).status_code == 403
    creo_record = _declare(client, "binil", creo, 2)
    _ok(client.post(f"{API}/records/{creo_record['id']}/archive", json={"reason": "No longer used"}, headers=_h(client, "binil")))

    _ok(client.post(f"{API}/records/{nx_record['id']}/archive", json={"reason": "Moved to surfacing"}, headers=_h(client, "anurag")))
    again = _declare(client, "binil", nx, 2)
    assert again["status"] == "self_declared"
    profile = _ok(client.get(f"{API}/me", headers=_h(client, "binil")))
    record = _record(profile, nx)
    assert record["verified_level"] is None and record["state"] == "claimed"
    assert [e["action"] for e in record["history"]][-2:] == ["archived", "redeclared"]
    assert record["history"][-2]["from_verified_level"] == 3  # history keeps the old verification
    assert session.scalar(select(func.count(UserSkill.id)).where(UserSkill.user_id == binil)) == 2  # nothing deleted


# ----------------------------------------------------------------- project experience


def test_project_experience_comes_from_real_projects_and_never_verifies(client, session):
    _teams(session)
    booked = _project(session)
    booked.designer_id = None
    booked.design_leader_id = IDS["user_anurag"]
    _book(session, booked.id, "12", user_id=IDS["user_binil"], status=TimesheetStatus.draft)
    _book(session, booked.id, "8", user_id=IDS["user_binil"], week_offset=1, status=TimesheetStatus.approved)
    unrelated = _project(session)
    unrelated.designer_id = IDS["user_ranjith"]
    session.commit()

    data = _ok(client.get(f"{API}/profiles/{IDS['user_binil']}/experience", headers=_h(client, "anurag")))
    rows = {r["project_id"]: r for r in data["projects"]}
    assert str(unrelated.id) not in rows
    seeded = rows[str(IDS["project"])]
    assert seeded["roles"] == ["designer"] and seeded["timesheet_only"] is False and seeded["cad_software"] is None
    timesheet = rows[str(booked.id)]
    assert timesheet["roles"] == [] and timesheet["timesheet_only"] is True
    assert timesheet["hours_total"] == 20
    assert timesheet["hours_by_status"] == {"draft": 12, "approved": 8}
    assert any("CAD software" in line for line in data["limitations"])
    assert session.scalar(select(func.count(UserSkill.id)).where(UserSkill.user_id == IDS["user_binil"])) == 0

    nx = _nx_id(session)
    record = _declare(client, "binil", nx, 3)
    _ok(client.post(f"{API}/records/{record['id']}/evidence", json={"project_id": str(IDS["project"])}, headers=_h(client, "binil")), 201)
    # Binil booked hours on `booked` but is not assigned, so project visibility hides it from him; his reviewer can cite it.
    assert client.post(f"{API}/records/{record['id']}/evidence", json={"project_id": str(booked.id)}, headers=_h(client, "binil")).status_code == 403
    _ok(client.post(f"{API}/records/{record['id']}/evidence", json={"project_id": str(booked.id), "note": "Electrode set"}, headers=_h(client, "anurag")), 201)
    refused = client.post(f"{API}/records/{record['id']}/evidence", json={"project_id": str(unrelated.id)}, headers=_h(client, "anurag"))
    assert refused.status_code == 400  # not connected to Binil
    evidence = _record(_ok(client.get(f"{API}/profiles/{IDS['user_binil']}", headers=_h(client, "anurag"))), nx)
    assert evidence["state"] == "claimed"  # evidence does not verify
    assert sorted((e["tool_number"], e["hours_total"]) for e in evidence["evidence"]) == sorted(
        [("T-100", None), (booked.tool_number, 20)]
    )
    own_view = _record(_ok(client.get(f"{API}/me", headers=_h(client, "binil"))), nx)
    hidden = next(e for e in own_view["evidence"] if not e["visible"])
    assert hidden["tool_number"] is None and hidden["note"] is None  # masked, not leaked


# ----------------------------------------------------------------- requirements and matching


def _next_monday() -> date:
    today = date.today()
    return today + timedelta(days=7 - today.weekday())


def test_matching_keeps_suitability_and_availability_separate(client, session):
    teams = _teams(session)
    nx = _nx_id(session)
    project_id = IDS["project"]
    assert client.put(f"{API}/projects/{project_id}/requirements", json={"skill_id": nx, "min_level": 3}, headers=_h(client, "readonly")).status_code == 403
    reqs = _ok(client.put(f"{API}/projects/{project_id}/requirements", json={"skill_id": nx, "min_level": 3}, headers=client.auth_headers))
    assert [(r["skill_name"], r["min_level"], r["is_mandatory"]) for r in reqs["requirements"]] == [("NX", 3, True)]

    _declare(client, "binil", nx, 4, submit=True)
    _assess(client, "anurag", IDS["user_binil"], nx, "verify", 4)
    _declare(client, "logesh", nx, 5)  # claim only
    binil = session.get(User, IDS["user_binil"])
    binil.availability_status = UserAvailabilityStatus.on_leave
    session.commit()
    designer_before = session.get(Project, project_id).designer_id

    body = {"project_id": str(project_id), "team_id": str(teams["a"]), "start": _next_monday().isoformat(), "periods": 2}
    result = _ok(client.post(f"{API}/match", json=body, headers=client.auth_headers))
    by_id = {c["user_id"]: c for c in result["candidates"]}
    skilled = by_id[str(IDS["user_binil"])]
    assert skilled["suitability"] == "confirmed"
    assert skilled["availability"] == "unavailable"  # skilled but on leave is not available
    claimed = by_id[str(teams["logesh"])]
    assert claimed["suitability"] == "unconfirmed"  # a claim is never a confirmed match
    assert claimed["availability"] != "unavailable"
    assert result["summary"]["confirmed_with_capacity_indicated"] == 0
    assert not [key for key in skilled if "score" in key]
    session.expire_all()
    assert session.get(Project, project_id).designer_id == designer_before  # recommendations never assign

    assert client.post(f"{API}/match", json=body, headers=_h(client, "binil")).status_code == 403


# ----------------------------------------------------------------- gaps and plans


def test_gap_report_counts_only_verified_and_flags_criticality_from_management(client, session):
    teams = _teams(session)
    critical = _skill(client, "Hot runner design", is_critical=True, min_verified_coverage=2)
    plain = _skill(client, "Electrode design", category="Fixture and tooling")
    report = _ok(client.get(f"{API}/gaps?team_id={teams['a']}", headers=client.auth_headers))
    row = next(s for s in report["skills"] if s["skill_id"] == critical)
    assert row["verified_count"] == 0 and row["no_record"] == row["population"] > 0
    assert "no_verified_coverage" in row["flags"]
    finding = next(f for f in report["findings"] if f["skill_id"] == critical)
    assert finding["code"] == "critical_no_verified_coverage" and "not confirmed absent" in finding["explanation"]

    for skill in (critical, plain):
        _declare(client, "binil", skill, 4, submit=True)
        _assess(client, "anurag", IDS["user_binil"], skill, "verify", 4)
        _declare(client, "logesh", skill, 5)  # unverified claims never count
    report = _ok(client.get(f"{API}/gaps?team_id={teams['a']}", headers=client.auth_headers))
    rows = {s["skill_id"]: s for s in report["skills"]}
    assert rows[critical]["verified_count"] == 1 and rows[critical]["claimed_unverified"] == 1
    assert {"single_verified_specialist", "below_coverage_target"} <= set(rows[critical]["flags"])
    codes = {(f["skill_id"], f["code"]) for f in report["findings"]}
    assert (critical, "critical_single_specialist") in codes and (critical, "critical_below_target") in codes
    plain_findings = [f for f in report["findings"] if f["skill_id"] == plain]
    assert [(f["code"], f["severity"]) for f in plain_findings] == [("single_specialist_dependency", "info")]
    assert rows[plain]["is_critical"] is False  # never inferred from a single holder
    depth = next(d for d in report["team_depth"] if d["team_id"] == str(teams["a"]) and d["skill_id"] == critical)
    assert depth["depth"] == "single"
    only_critical = _ok(client.get(f"{API}/gaps?critical_only=true", headers=client.auth_headers))
    assert {s["skill_id"] for s in only_critical["skills"]} == {critical}


def test_development_plan_never_changes_proficiency(client, session):
    _teams(session)
    nx = _nx_id(session)
    binil = IDS["user_binil"]
    _declare(client, "binil", nx, 3, submit=True)
    _assess(client, "anurag", binil, nx, "verify", 3)
    body = {"user_id": str(binil), "skill_id": nx, "target_level": 4, "objective": "Lead NX surfacing on two tools",
            "training_required": True, "training_requirement": "NX advanced surfacing course",
            "mentor_id": str(IDS["user_anurag"]), "target_review_date": (date.today() + timedelta(days=90)).isoformat()}
    assert client.post(f"{API}/plans", json=body, headers=_h(client, "binil")).status_code == 403
    assert client.post(f"{API}/plans", json={**body, "target_level": 3}, headers=_h(client, "anurag")).status_code == 400
    plan = _ok(client.post(f"{API}/plans", json=body, headers=_h(client, "anurag")), 201)
    assert plan["baseline_verified_level"] == 3 and plan["status"] == "planned"

    gaps = _ok(client.get(f"{API}/gaps", headers=client.auth_headers))
    assert [t["training_requirement"] for t in gaps["training"] if t["user_id"] == str(binil)] == ["NX advanced surfacing course"]
    done = _ok(client.put(f"{API}/plans/{plan['id']}", json={**body, "status": "completed", "progress_note": "Course finished"}, headers=_h(client, "anurag")))
    assert done["status"] == "completed" and done["completed_at"] is not None
    session.expire_all()
    record = session.scalar(select(UserSkill).where(UserSkill.user_id == binil, UserSkill.skill_id == uuid.UUID(nx)))
    assert (record.status, record.verified_level) == ("verified", 3)  # completion is not verification
    mine = _ok(client.get(f"{API}/plans?include_closed=true", headers=_h(client, "binil")))
    assert [p["id"] for p in mine] == [plan["id"]]


# ----------------------------------------------------------------- legacy endpoints


def test_legacy_settings_skill_endpoints_are_authenticated_and_non_destructive(client, session):
    _teams(session)
    nx = _nx_id(session)
    creo = str(session.scalar(select(Skill.id).where(Skill.name == "Creo")))
    binil = IDS["user_binil"]
    assert client.get("/api/v1/settings/skills").status_code == 401
    assert client.get(f"/api/v1/settings/users/{binil}/skills", headers=_h(client, "logesh")).status_code == 403
    _declare(client, "binil", nx, 3, submit=True)
    _assess(client, "anurag", binil, nx, "verify", 3)
    _declare(client, "binil", creo, 2)
    assert {r["skill_id"] for r in _ok(client.get(f"/api/v1/settings/users/{binil}/skills", headers=_h(client, "binil")))} == {nx, creo}

    put = client.put(f"/api/v1/settings/users/{binil}/skills", json=[{"skill_id": nx, "proficiency": "advanced"}], headers=client.auth_headers)
    assert put.status_code == 200, put.text
    assert [r["skill_id"] for r in put.json()] == [nx]
    session.expire_all()
    rows = {str(r.skill_id): r for r in session.scalars(select(UserSkill).where(UserSkill.user_id == binil)).all()}
    assert rows[creo].status == "archived"  # archived, not deleted
    assert (rows[nx].status, rows[nx].verified_level, rows[nx].proficiency) == ("verified", 3, SkillLevel.advanced)


# ----------------------------------------------------------------- migrations


def test_phase109_migration_preserves_existing_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    skill_id, user_id, record_id = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE skills (id CHAR(32) PRIMARY KEY, tenant_id CHAR(32), name VARCHAR(100) NOT NULL, "
            "category VARCHAR(100), is_active BOOLEAN NOT NULL, created_at DATETIME, updated_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE user_skills (id CHAR(32) PRIMARY KEY, tenant_id CHAR(32), user_id CHAR(32) NOT NULL, "
            "skill_id CHAR(32) NOT NULL, proficiency VARCHAR(12) NOT NULL, created_at DATETIME, updated_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO skills VALUES (:id, NULL, 'NX', 'CAD', 1, '2025-01-01', '2025-01-01')"), {"id": skill_id})
        conn.execute(
            text("INSERT INTO user_skills VALUES (:id, NULL, :u, :s, 'advanced', '2025-01-01', '2025-01-01')"),
            {"id": record_id, "u": user_id, "s": skill_id},
        )
    ensure_phase109_engineering_skills_foundation(engine)
    ensure_phase109_engineering_skills_foundation(engine)  # idempotent
    with engine.connect() as conn:
        skill = conn.execute(text("SELECT name, category, is_active, kind, is_critical, sort_order FROM skills")).one()
        record = conn.execute(text(
            "SELECT user_id, skill_id, proficiency, status, origin, declared_level, verified_level, verified_at FROM user_skills"
        )).one()
        counts = (conn.execute(text("SELECT COUNT(*) FROM skills")).scalar(), conn.execute(text("SELECT COUNT(*) FROM user_skills")).scalar())
    assert tuple(skill) == ("NX", "CAD", 1, None, 0, 0)
    assert tuple(record) == (user_id, skill_id, "advanced", "pending_verification", "legacy", None, None, None)
    assert counts == (1, 1)
    engine.dispose()


def test_phase7_seed_does_not_recreate_a_renamed_skill(test_engine, session):
    nx = session.scalar(select(Skill).where(Skill.name == "NX"))
    nx.name = "Siemens NX"
    nx.aliases = '["NX", "Unigraphics"]'
    session.commit()
    ensure_phase7_foundation(test_engine)
    session.expire_all()
    names = set(session.scalars(select(Skill.name)).all())
    assert "Siemens NX" in names and "NX" not in names


# ----------------------------------------------------------------- Control Tower


def _verify(session: Session, user_id, skill_id, level: int) -> UserSkill:
    row = UserSkill(user_id=user_id, skill_id=skill_id, proficiency=SkillLevel.advanced, status="verified",
                    origin="manager", verified_level=level, declared_level=level, verified_at=datetime(2026, 1, 5, 9))
    session.add(row)
    session.flush()
    return row


def test_control_tower_capability_rules(session):
    nx = session.scalar(select(Skill).where(Skill.name == "NX"))
    creo = session.scalar(select(Skill).where(Skill.name == "Creo"))
    project_id = IDS["project"]
    session.add(ProjectSkillRequirement(project_id=project_id, skill_id=nx.id, min_level=3, is_mandatory=True))
    session.flush()

    def findings():
        _projects, detections = detect_all(session, date.today())
        return {d.rule_id: d for d in detections if d.project_id == project_id and d.rule.category == "capability"}

    _verify(session, IDS["user_ranjith"], nx.id, 2)  # verified, but below the minimum
    uncovered = findings()
    assert set(uncovered) == {"skill_requirement_uncovered"}
    assert uncovered["skill_requirement_uncovered"].severity == "medium"
    assert "does not prove" in uncovered["skill_requirement_uncovered"].explanation
    assert "delayed" in uncovered["skill_requirement_uncovered"].explanation  # states it is not a delay

    _verify(session, IDS["user_binil"], nx.id, 3)
    assert set(findings()) == {"skill_requirement_single_specialist"}

    session.add(ProjectSkillRequirement(project_id=project_id, skill_id=creo.id, min_level=2, is_mandatory=True))
    _verify(session, IDS["user_anurag"], creo.id, 4)
    anurag_nx = _verify(session, IDS["user_anurag"], nx.id, 2)
    assert set(findings()) == {"skill_no_confirmed_candidate", "skill_requirement_single_specialist"}
    _verify(session, IDS["user_ranjith"], creo.id, 2)
    anurag_nx.verified_level = 4
    session.flush()
    assert set(findings()) == set()  # Anurag now covers both; Binil and Anurag hold NX, Anurag and Ranjith hold Creo
    assert {r.category for r in rule_catalog() if r.rule_id.startswith("skill_")} == {"capability"}
    session.rollback()
