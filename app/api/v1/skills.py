"""Engineering skills API: taxonomy, verified profiles, matrix, gaps, plans and matching."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.permissions import can_read_project, can_update_project
from app.core.team_access import resolve_team_scope
from app.models.models import Project, Team, User
from app.schemas.skills import (
    ArchiveWrite,
    AssessmentWrite,
    CategoryRename,
    DeclarationWrite,
    EvidenceWrite,
    MatchRequest,
    PlanWrite,
    ProficiencyLevelWrite,
    RelationshipWrite,
    RequirementWrite,
    SkillWrite,
)
from app.services.skills import (
    experience,
    gaps,
    matching,
    plans,
    profiles,
    taxonomy,
    views,
)
from app.services.skills.access import SkillAccess, resolve_skill_access
from app.services.skills.errors import SkillError

router = APIRouter(prefix="/skills", tags=["skills"])

_STATES = {"no_record", "claimed", "verified", "reassessment", "rejected"}


def _access(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SkillAccess:
    return resolve_skill_access(db, current_user)


def _forbid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _fail(exc: SkillError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"message": exc.message, **exc.detail} if exc.detail else exc.message)


def _require_taxonomy(access: SkillAccess) -> None:
    if not access.can_manage_taxonomy:
        raise _forbid("Managing the skills taxonomy requires administrator or HR configure access")


def _subject(db: Session, access: SkillAccess, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if not access.can_view_profile(db, user_id):
        raise _forbid("Skill profile access denied")
    return user


def _project(db: Session, user: User, project_id: UUID, *, write: bool) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    allowed = can_update_project(db, user, project) if write else can_read_project(db, user, project)
    if not allowed:
        raise _forbid("Project access denied")
    return project


def _skill_input(payload: SkillWrite) -> taxonomy.SkillInput:
    return taxonomy.SkillInput(**payload.model_dump())


# --- Access and taxonomy ---------------------------------------------------


@router.get("/access")
def get_access(access: SkillAccess = Depends(_access)):
    return {
        "can_manage_taxonomy": access.can_manage_taxonomy,
        "can_view_others": access.can_view_others,
        "can_review": access.can_review_anyone,
        "can_match_resources": access.can_match_resources,
    }


@router.get("/taxonomy")
def get_taxonomy(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    access: SkillAccess = Depends(_access),
):
    return views.taxonomy_read(db, include_inactive=include_inactive and access.can_manage_taxonomy)


@router.post("/taxonomy/skills", status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        skill = taxonomy.create_skill(db, _skill_input(payload), actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": skill.id, "name": skill.name}


@router.put("/taxonomy/skills/{skill_id}")
def update_skill(skill_id: UUID, payload: SkillWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        skill = taxonomy.update_skill(db, taxonomy.get_skill(db, skill_id), _skill_input(payload), actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": skill.id, "name": skill.name}


@router.post("/taxonomy/categories/rename")
def rename_category(payload: CategoryRename, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        count = taxonomy.rename_category(db, old=payload.old, new=payload.new, actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"updated": count}


@router.post("/taxonomy/relationships", status_code=status.HTTP_201_CREATED)
def add_relationship(payload: RelationshipWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        row = taxonomy.add_relationship(db, **payload.model_dump(), actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": row.id}


@router.delete("/taxonomy/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_relationship(relationship_id: UUID, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        taxonomy.remove_relationship(db, relationship_id, actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()


@router.put("/taxonomy/levels/{level}")
def update_level(level: int, payload: ProficiencyLevelWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    try:
        taxonomy.update_proficiency_level(db, level=level, name=payload.name, description=payload.description, actor=access.user)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return taxonomy.proficiency_framework(db)


@router.post("/taxonomy/standard-pack")
def load_standard_pack(dry_run: bool = Query(True), db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _require_taxonomy(access)
    result = taxonomy.load_standard_taxonomy(db, actor=access.user, dry_run=dry_run)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return result


# --- Profiles and verification ---------------------------------------------


@router.get("/me")
def my_profile(db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    return views.profile_read(db, access, access.user, include_archived=True)


@router.get("/profiles/{user_id}")
def get_profile(user_id: UUID, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    subject = _subject(db, access, user_id)
    return views.profile_read(db, access, subject, include_archived=access.can_review(db, user_id) or user_id == access.user.id)


@router.get("/profiles/{user_id}/experience")
def get_experience(user_id: UUID, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    _subject(db, access, user_id)
    return experience.project_experience(db, access.user, user_id)


@router.post("/me/declarations")
def declare(payload: DeclarationWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        record = profiles.declare_skill(db, access, profiles.Declaration(**payload.model_dump()))
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": record.id, "status": record.status}


@router.post("/records/{record_id}/submit")
def submit(record_id: UUID, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        record = profiles.submit_for_verification(db, access, profiles.get_record(db, record_id))
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": record.id, "status": record.status}


@router.post("/records/{record_id}/archive")
def archive(record_id: UUID, payload: ArchiveWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        record = profiles.get_record(db, record_id)
        if not access.can_view_profile(db, record.user_id):
            raise _forbid("Skill profile access denied")
        record = profiles.archive_record(db, access, record, reason=payload.reason)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": record.id, "status": record.status}


@router.post("/profiles/{user_id}/assess")
def assess(user_id: UUID, payload: AssessmentWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        record = profiles.assess(
            db,
            access,
            subject_id=user_id,
            skill_id=payload.skill_id,
            data=profiles.Assessment(
                decision=payload.decision,
                level=payload.level,
                method=payload.method,
                feedback=payload.feedback,
                confidential_note=payload.confidential_note,
            ),
        )
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": record.id, "status": record.status, "verified_level": record.verified_level}


@router.post("/records/{record_id}/evidence", status_code=status.HTTP_201_CREATED)
def add_evidence(record_id: UUID, payload: EvidenceWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        row = experience.add_evidence(db, access, profiles.get_record(db, record_id), project_id=payload.project_id, note=payload.note)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"id": row.id}


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_evidence(evidence_id: UUID, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    try:
        experience.remove_evidence(db, access, evidence_id)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()


# --- Matrix, review queue and gaps -----------------------------------------


def _team_filter(db: Session, access: SkillAccess, team_id: UUID | None) -> None:
    if team_id is None:
        return
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown team")
    if access.view_team_ids is not None and team_id not in access.view_team_ids:
        raise _forbid("Team is outside your skills scope")


@router.get("/matrix")
def get_matrix(
    team_id: UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    software_skill_id: UUID | None = None,
    min_level: int | None = Query(default=None, ge=1, le=5),
    state: list[str] | None = Query(default=None),
    q: str | None = None,
    critical_only: bool = False,
    db: Session = Depends(get_db),
    access: SkillAccess = Depends(_access),
):
    if not access.can_view_others:
        raise _forbid("The skills matrix is available to managers, reviewers, HR and resource planners")
    _team_filter(db, access, team_id)
    states = set(state or []) & _STATES or None
    return views.matrix_read(
        db,
        access,
        team_id=team_id,
        category=category,
        kind=kind,
        software_skill_id=software_skill_id,
        min_level=min_level,
        states=states,
        q=q,
        critical_only=critical_only,
    )


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    if not access.can_review_anyone:
        raise _forbid("You are not a skills reviewer")
    return views.review_queue(db, access)


@router.get("/gaps")
def get_gaps(
    team_id: UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    critical_only: bool = False,
    min_level: int = Query(default=1, ge=1, le=5),
    skill_id: list[UUID] | None = Query(default=None),
    db: Session = Depends(get_db),
    access: SkillAccess = Depends(_access),
):
    if not access.can_view_others:
        raise _forbid("Skills gap analysis is available to managers, reviewers, HR and resource planners")
    _team_filter(db, access, team_id)
    return gaps.build_gap_report(
        db,
        access,
        team_id=team_id,
        category=category,
        kind=kind,
        critical_only=critical_only,
        min_level=min_level,
        skill_ids=set(skill_id) if skill_id else None,
    )


# --- Development plans -----------------------------------------------------


@router.get("/plans")
def get_plans(
    user_id: UUID | None = None,
    include_closed: bool = False,
    db: Session = Depends(get_db),
    access: SkillAccess = Depends(_access),
):
    if user_id is not None:
        _subject(db, access, user_id)
        scope = {user_id}
    else:
        if not access.can_view_others:
            scope = {access.user.id}
        else:
            scope = access.visible_user_ids(db)
    return plans.plan_reads(db, plans.list_plans(db, user_ids=scope, include_closed=include_closed))


@router.post("/plans", status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    if payload.user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")
    data = plans.PlanInput(**payload.model_dump(exclude={"user_id"}))
    try:
        plan = plans.create_plan(db, access, subject_id=payload.user_id, data=data)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return plans.plan_reads(db, [plan])[0]


@router.put("/plans/{plan_id}")
def update_plan(plan_id: UUID, payload: PlanWrite, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    data = plans.PlanInput(**payload.model_dump(exclude={"user_id"}))
    try:
        plan = plans.update_plan(db, access, plans.get_plan(db, plan_id), data)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return plans.plan_reads(db, [plan])[0]


# --- Project requirements and matching -------------------------------------


def _requirement_reads(db: Session, project: Project) -> list[dict]:
    names = taxonomy.level_names(db)
    rows = matching.project_requirements(db, project.id)
    return [
        {
            "id": r.id,
            "skill_id": r.skill_id,
            "skill_name": r.skill.name if r.skill else None,
            "skill_is_active": bool(r.skill.is_active) if r.skill else False,
            "min_level": r.min_level,
            "min_level_name": names.get(r.min_level),
            "is_mandatory": bool(r.is_mandatory),
            "note": r.note,
        }
        for r in rows
    ]


@router.get("/projects/{project_id}/requirements")
def get_requirements(project_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = _project(db, current_user, project_id, write=False)
    return {
        "project_id": project.id,
        "can_edit": can_update_project(db, current_user, project),
        "requirements": _requirement_reads(db, project),
    }


@router.put("/projects/{project_id}/requirements")
def put_requirement(
    project_id: UUID,
    payload: RequirementWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project(db, current_user, project_id, write=True)
    try:
        matching.set_requirement(db, project=project, actor=current_user, **payload.model_dump())
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"project_id": project.id, "can_edit": True, "requirements": _requirement_reads(db, project)}


@router.delete("/projects/{project_id}/requirements/{requirement_id}")
def delete_requirement(
    project_id: UUID,
    requirement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _project(db, current_user, project_id, write=True)
    try:
        matching.remove_requirement(db, project=project, requirement_id=requirement_id)
    except SkillError as exc:
        db.rollback()
        raise _fail(exc) from exc
    db.commit()
    return {"project_id": project.id, "can_edit": True, "requirements": _requirement_reads(db, project)}


@router.post("/match")
def match(payload: MatchRequest, db: Session = Depends(get_db), access: SkillAccess = Depends(_access)):
    if not access.can_match_resources:
        raise _forbid("Candidate recommendations require Resource Planning access")
    if payload.team_id is not None and db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown team")
    team_ids = resolve_team_scope(db, access.user, team_id=payload.team_id)
    if payload.team_id is not None and team_ids is not None and payload.team_id not in team_ids:
        raise _forbid("Team is outside your accessible scope")
    if payload.requirements:
        specs = [matching.RequirementSpec(**r.model_dump()) for r in payload.requirements]
    elif payload.project_id is not None:
        project = _project(db, access.user, payload.project_id, write=False)
        specs = [
            matching.RequirementSpec(skill_id=r.skill_id, min_level=r.min_level, is_mandatory=r.is_mandatory)
            for r in matching.project_requirements(db, project.id)
        ]
        if not specs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This project has no skill requirements yet")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Give a project or a list of requirements")
    if payload.project_id is not None and payload.requirements:
        _project(db, access.user, payload.project_id, write=False)
    try:
        result = matching.recommend_candidates(
            db,
            requirements=specs,
            team_ids=team_ids,
            start=payload.start,
            granularity=payload.granularity,
            periods=payload.periods,
        )
    except SkillError as exc:
        raise _fail(exc) from exc
    db.rollback()
    return result
