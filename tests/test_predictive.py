"""Phase 7 predictive intelligence: deterministic datasets, no external model or AI calls."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectStage
from app.models.models import Milestone, Project, ProjectStageEstimate, ProjectType, Team
from app.models.prediction import (
    INSUFFICIENT,
    MODEL_ACTIVE,
    MODEL_CANDIDATE,
    OUTCOME_EVALUATED,
    OUTCOME_NOT_EVALUABLE,
    OUTCOME_PENDING,
    PREDICTED,
    RUN_FAILED,
    Prediction,
    PredictionModelVersion,
    PredictionRun,
    PredictionSetting,
)
from app.services.predictive import engine, registry
from app.services.predictive.delivery import CapacityCheck, duration_samples, predict_delivery
from app.services.predictive.evaluation import HOURS_SETTLE_DAYS, evaluate_outcomes
from app.services.predictive.hours import hours_samples, predict_final_hours
from app.services.predictive.inputs import comparable_group, load_facts
from app.services.predictive.milestone import load_milestones, milestone_samples, predict_project_milestones
from app.services.predictive.resources import (
    BACKLOG_DAYS,
    PersonSupply,
    build_outcomes,
    non_project_shares,
    project_demands,
)
from app.models.finance import QuotePaymentLine
from app.services.forecasting.finance import build_finance_forecast
from app.services.predictive.finance import (
    completions_for,
    invoice_lags,
    load_ledgers,
    payment_delays,
    predict_billing,
    predict_collections,
)
from app.services.predictive.patterns import project_patterns
from app.services.predictive.stats import mann_whitney_p, quantile
from app.services.predictive.types import Outcome
from tests.test_engineering_metrics import _book, _project
from tests.test_forecasting import _finance_team, _invoice, _quote
from tests.test_forecasting import _milestone as _fin_milestone
from tests.test_stage_delivery_metrics import _completed, _estimate, _staged

PRE = ProjectStage.preliminary
AS_OF = date(2025, 12, 1)


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    registry.unregister_versions()
    engine.unregister_generator("project_final_hours", "hours-2")


def _history(session, actuals: list[str], *, estimate: str = "100", durations: list[int] | None = None,
             project_type: ProjectType | None = None, prefix: str = "H") -> list[Project]:
    """Completed projects with an approved stage estimate, recorded hours and (optionally) a start date."""
    rows = []
    for i, actual in enumerate(actuals):
        completed = datetime(2025, 9, 1 + i, 12)
        project = _completed(session, f"{prefix}-{i}", completed=completed)
        project.project_type_id = project_type.id if project_type else None
        if durations:
            project.actual_start_date = completed.date() - timedelta(days=durations[i])
        _staged(session, project, {PRE: estimate}, {PRE: actual})
        rows.append(project)
    session.flush()
    return rows


def _open(session, *, estimate: str | None = "100", actual: str = "0", started_days_ago: int | None = None,
          due_in: int = 60, project_type: ProjectType | None = None) -> Project:
    project = _project(session, quoted="300")
    project.project_type_id = project_type.id if project_type else None
    project.due_date = AS_OF + timedelta(days=due_in)
    if started_days_ago is not None:
        project.actual_start_date = AS_OF - timedelta(days=started_days_ago)
    if estimate:
        _estimate(session, project.id, PRE, estimate)
    if actual != "0":
        _book(session, project.id, actual, week_offset=20)
    session.flush()
    return project


def _facts(session, project):
    return load_facts(session, [project], AS_OF)[project.id]


def _history_facts(session, rows):
    return list(load_facts(session, rows, AS_OF).values())


# ----------------------------------------------------------------- statistics


def test_quantile_and_rank_test_are_deterministic():
    assert quantile([1, 2, 3, 4], 0.5) == 2.5
    assert quantile([10], 0.9) == 10
    assert mann_whitney_p([1, 2, 3, 4], [5, 6, 7, 8, 9]) is None  # a side below 5: no test
    p = mann_whitney_p([10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6])
    assert p is not None and p < 0.05


# ----------------------------------------------------------------- final hours


def test_final_hours_from_comparable_history(session):
    history = _history(session, ["110", "120", "130", "140", "150"])
    project = _open(session, actual="40")
    session.commit()
    out = predict_final_hours(_facts(session, project), hours_samples(_history_facts(session, history)), AS_OF)
    assert out.status == PREDICTED
    assert out.predicted_value == Decimal("130.00")  # median ratio 1.3 × original 100
    assert out.baseline_value == Decimal("100") and out.variance_value == Decimal("30.00")
    assert out.observed_frequency == Decimal("1.0")  # all 5 comparable outcomes above the approved 100 h
    assert out.lower_value is None and out.upper_value is None  # range needs 10 outcomes
    assert out.sample_size == 5 and "same project type" in out.comparison_group
    assert out.data_used["quoted_hours"] == "300.00"
    names = {f["name"]: f for f in out.factors}
    assert names["Hours recorded so far"]["role"] == "calculation"
    assert names["Expected remaining hours"]["value"] == "90.00"


def test_final_hours_never_below_recorded_and_ranges_need_ten(session):
    history = _history(session, [str(105 + 5 * i) for i in range(10)])  # ratios 1.05 … 1.50
    project = _open(session, actual="40")
    late = _open(session, actual="140")
    session.commit()
    samples = hours_samples(_history_facts(session, history))
    out = predict_final_hours(_facts(session, project), samples, AS_OF)
    assert out.lower_value == Decimal("109.50") and out.upper_value == Decimal("145.50")
    assert "10th–90th percentile of 10" in out.range_basis
    beyond = predict_final_hours(_facts(session, late), samples, AS_OF)
    assert beyond.status == INSUFFICIENT and beyond.predicted_value is None
    assert "already recorded" in beyond.reason


def test_insufficient_history_and_quoted_hours_alone(session):
    history = _history(session, ["110", "120", "130", "140"])
    project = _open(session)
    quoted_only = _open(session, estimate=None)
    session.commit()
    samples = hours_samples(_history_facts(session, history))
    few = predict_final_hours(_facts(session, project), samples, AS_OF)
    assert few.status == INSUFFICIENT and few.predicted_value is None
    assert "Only 4 completed project(s)" in few.reason
    quoted = predict_final_hours(_facts(session, quoted_only), samples, AS_OF)
    assert quoted.status == INSUFFICIENT and "Quoted hours" in quoted.reason


def test_other_project_types_are_never_pooled(session):
    tool = ProjectType(name="Tool design")
    fixture = ProjectType(name="Fixture design")
    session.add_all([tool, fixture])
    session.flush()
    history = _history(session, ["110", "120", "130", "140", "150"], project_type=tool)
    same = _open(session, project_type=tool)
    other = _open(session, project_type=fixture)
    untyped = _open(session)
    session.commit()
    samples = hours_samples(_history_facts(session, history))
    assert predict_final_hours(_facts(session, same), samples, AS_OF).status == PREDICTED
    for project in (other, untyped):
        out = predict_final_hours(_facts(session, project), samples, AS_OF)
        assert out.status == INSUFFICIENT and "Only 0" in out.reason


def test_customer_only_refines_a_group_of_the_same_type(session):
    history = _history(session, ["110", "120", "130", "140", "150"])
    project = _open(session)
    session.commit()
    target = _facts(session, project)
    samples = hours_samples(_history_facts(session, history))
    label, group, largest = comparable_group(target, samples)
    assert label.startswith("same project type, complexity and customer") and len(group) == 5
    assert label.endswith("(projects without a project type)")
    elsewhere = target.with_changes(customer_id=None)
    label, group, _ = comparable_group(elsewhere, samples)
    assert label.startswith("same project type and complexity")
    assert comparable_group(target, samples, minimum=6) == (None, [], 5)


# ----------------------------------------------------------------- delivery


def test_delivery_from_elapsed_time_and_comparable_durations(session):
    history = _history(session, ["120"] * 5, durations=[50, 60, 70, 80, 90])
    project = _open(session, started_days_ago=30, due_in=20)
    session.commit()
    facts = _facts(session, project)
    out = predict_delivery(facts, duration_samples(_history_facts(session, history)), AS_OF)
    assert out.status == PREDICTED
    assert out.predicted_date == facts.start_date + timedelta(days=70)
    assert out.baseline_date == AS_OF + timedelta(days=20)
    assert out.variance_value == Decimal(20)  # 70 days from start = 40 from today, target in 20
    assert out.observed_frequency == Decimal("0.8")  # 4 of 5 comparable durations exceed the 50 days available
    assert {f["name"] for f in out.factors} >= {"Comparable projects", "Days elapsed since start"}
    assert out.data_used["start_source"] == "actual start"


def test_delivery_refuses_without_start_or_when_past_history(session):
    history = _history(session, ["120"] * 5, durations=[50, 60, 70, 80, 90])
    unstarted = _open(session)
    overrun = _open(session, started_days_ago=75)
    session.commit()
    samples = duration_samples(_history_facts(session, history))
    no_start = predict_delivery(_facts(session, unstarted), samples, AS_OF)
    assert no_start.status == INSUFFICIENT and "No start date" in no_start.reason
    long = predict_delivery(_facts(session, overrun), samples, AS_OF)
    assert long.status == INSUFFICIENT and long.predicted_date is None
    assert "already run 75 days" in long.reason


def test_milestone_counts_do_not_drive_the_delivery_date(session):
    history = _history(session, ["120"] * 5, durations=[50, 60, 70, 80, 90])
    project = _open(session, started_days_ago=30)
    session.commit()
    facts = _facts(session, project)
    samples = duration_samples(_history_facts(session, history))
    base = predict_delivery(facts, samples, AS_OF)
    busy = predict_delivery(facts.with_changes(overdue_milestones=4, open_milestones=6), samples, AS_OF)
    assert busy.predicted_date == base.predicted_date
    roles = {f["name"]: f["role"] for f in busy.factors}
    assert roles["Overdue milestones"] == "context"


# ----------------------------------------------------------------- engine, history, evaluation


def _latest(session, prediction_type, project_id) -> Prediction:
    return session.scalar(
        select(Prediction).where(
            Prediction.prediction_type == prediction_type,
            Prediction.project_id == project_id,
            Prediction.is_latest.is_(True),
            Prediction.is_shadow.is_(False),
        )
    )


def test_run_persists_predictions_without_touching_projects(session):
    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    project = _open(session, actual="40", started_days_ago=30)
    bare = _open(session, estimate=None)
    session.commit()
    before = (project.due_date, project.actual_hours, project.forecast_completion_date, project.execution_status)
    estimates = [(e.original_hours, e.current_hours) for e in session.scalars(select(ProjectStageEstimate))]

    run = engine.run_predictions(session, as_of=AS_OF)
    assert run.status == "succeeded"
    counts = json.loads(run.counts_json)
    open_count = len(engine.open_projects(session))  # includes the seeded TEST-001
    assert counts["project_final_hours"][PREDICTED] == 1
    assert counts["project_final_hours"][INSUFFICIENT] == open_count - 1
    hours_row = _latest(session, "project_final_hours", project.id)
    assert hours_row.model_version == "hours-1" and hours_row.predicted_value == Decimal("130.00")
    assert hours_row.outcome_status == OUTCOME_PENDING and hours_row.counts_for_accuracy
    assert json.loads(hours_row.factors_json)[0]["name"] == "Comparable projects"
    empty = _latest(session, "project_final_hours", bare.id)
    assert empty.status == INSUFFICIENT and empty.outcome_status == OUTCOME_NOT_EVALUABLE
    assert _latest(session, "project_delivery", project.id).predicted_date is not None

    session.refresh(project)
    assert (project.due_date, project.actual_hours, project.forecast_completion_date, project.execution_status) == before
    assert [(e.original_hours, e.current_hours) for e in session.scalars(select(ProjectStageEstimate))] == estimates
    settings = {s.prediction_type: s for s in session.scalars(select(PredictionSetting))}
    assert set(settings) == set(registry.TYPES) and settings["project_delivery"].active_version == "delivery-1"


def test_reruns_preserve_history_and_score_only_the_last_of_a_day(session):
    _history(session, ["110", "120", "130", "140", "150"])
    project = _open(session, actual="40")
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    engine.run_predictions(session, as_of=AS_OF)
    engine.run_predictions(session, as_of=AS_OF + timedelta(days=1))
    rows = session.scalars(
        select(Prediction).where(Prediction.prediction_type == "project_final_hours", Prediction.project_id == project.id)
        .order_by(Prediction.as_of, Prediction.created_at)
    ).all()
    assert len(rows) == 3
    first, second, third = rows
    assert not first.is_latest and not first.counts_for_accuracy and first.outcome_note.startswith("Replaced")
    assert not second.is_latest and second.counts_for_accuracy and second.superseded_at is not None
    assert third.is_latest and third.counts_for_accuracy


def test_outcomes_are_scored_against_actuals(session):
    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    project = _open(session, actual="40", started_days_ago=30)
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    finished = AS_OF + timedelta(days=45)
    _book(session, project.id, "80", week_offset=30)  # final actual 120 h
    project.execution_status = ExecutionStatus.completed
    project.completed_at = datetime.combine(finished, datetime.min.time())
    session.commit()

    evaluate_outcomes(session, finished + timedelta(days=HOURS_SETTLE_DAYS - 1))
    delivery_row = _latest(session, "project_delivery", project.id)
    hours_row = _latest(session, "project_final_hours", project.id)
    assert delivery_row.outcome_status == OUTCOME_EVALUATED and hours_row.outcome_status == OUTCOME_PENDING
    # predicted start + 70 days = 40 days out; finished at 45
    assert delivery_row.actual_date == finished and delivery_row.error_value == Decimal(-5)
    assert delivery_row.naive_abs_error == Decimal(15)  # target was AS_OF + 60
    assert delivery_row.event_occurred is False and delivery_row.horizon_days == 45

    evaluate_outcomes(session, finished + timedelta(days=HOURS_SETTLE_DAYS))
    session.refresh(hours_row)
    assert hours_row.outcome_status == OUTCOME_EVALUATED
    assert hours_row.actual_value == Decimal("120.00") and hours_row.error_value == Decimal("10.00")
    assert hours_row.pct_error == Decimal("8.33") and hours_row.naive_abs_error == Decimal("20.00")
    assert hours_row.event_occurred is True  # 120 h exceeded the approved 100 h


def test_cancelled_projects_are_not_scored(session):
    _history(session, ["110", "120", "130", "140", "150"])
    project = _open(session, actual="40")
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    project.execution_status = ExecutionStatus.cancelled
    session.commit()
    evaluate_outcomes(session, AS_OF + timedelta(days=60))
    row = _latest(session, "project_final_hours", project.id)
    assert row.outcome_status == OUTCOME_NOT_EVALUABLE and row.outcome_note == "The project was cancelled."


def test_failed_run_keeps_nothing_but_the_failure(session, monkeypatch):
    _history(session, ["110", "120", "130", "140", "150"])
    _open(session, actual="40")
    session.commit()

    def boom(ctx):
        raise RuntimeError("model exploded")

    monkeypatch.setitem(engine.GENERATORS, ("project_delivery", "delivery-1"), boom)
    with pytest.raises(RuntimeError):
        engine.run_predictions(session, as_of=AS_OF)
    run = session.scalar(select(PredictionRun))
    assert run.status == RUN_FAILED and "model exploded" in run.error
    assert session.scalars(select(Prediction)).all() == []


def test_disabled_types_do_not_run_and_candidates_run_in_shadow(session):
    _history(session, ["110", "120", "130", "140", "150"])
    project = _open(session, actual="40")
    session.commit()
    registry.sync(session)
    delivery_setting = session.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == "project_delivery"))
    delivery_setting.is_enabled = False
    registry.register_version("project_final_hours", registry.ModelSpec("hours-2", "Test candidate."))

    def candidate(ctx):
        outs = engine._final_hours(ctx)
        for o in outs:
            if o.predicted_value is not None:
                o.predicted_value += 1
        return outs

    engine.register_generator("project_final_hours", "hours-2", candidate)
    session.commit()
    run = engine.run_predictions(session, as_of=AS_OF)
    counts = json.loads(run.counts_json)
    assert counts["project_delivery"] == {"disabled": True}
    assert counts["project_final_hours"]["shadow"] == {"hours-2": 1}
    versions = {v.version: v.status for v in session.scalars(select(PredictionModelVersion))}
    assert versions["hours-1"] == MODEL_ACTIVE and versions["hours-2"] == MODEL_CANDIDATE
    shadow = session.scalar(select(Prediction).where(Prediction.model_version == "hours-2", Prediction.project_id == project.id))
    assert shadow.is_shadow and shadow.predicted_value == Decimal("131.00")
    assert _latest(session, "project_final_hours", project.id).predicted_value == Decimal("130.00")
    assert session.scalars(select(Prediction).where(Prediction.prediction_type == "project_delivery")).all() == []


# ----------------------------------------------------------------- milestones


def _ms(session, project, name, *, template=None, start=None, target=None, actual_start=None, completed=None,
        depends=None, sort=0, status=None) -> Milestone:
    row = Milestone(
        project_id=project.id, name=name, sort_order=sort, template_milestone_id=template,
        baseline_start_date=start, due_date=target, actual_start_date=actual_start, completed_date=completed,
        status=status or (MilestoneStatus.completed if completed else MilestoneStatus.not_started),
        depends_on_ids=json.dumps([str(d) for d in depends]) if depends else None,
    )
    session.add(row)
    session.flush()
    return row


def _milestone_history(session, template, ratios=(1.0, 1.2, 1.4, 1.6, 1.8), planned=10):
    for i, ratio in enumerate(ratios):
        project = _completed(session, f"MH-{template.hex[:4]}-{i}", completed=datetime(2025, 8, 1, 12))
        start = date(2025, 6, 1) + timedelta(days=i)
        _ms(session, project, "Design", template=template, start=start, target=start + timedelta(days=planned),
            actual_start=start, completed=start + timedelta(days=round(planned * ratio)))


def _ms_outcomes(session, project):
    rows = load_milestones(session, [project])[project.id]
    history = load_milestones(session, list(session.scalars(select(Project).where(Project.execution_status == ExecutionStatus.completed))))
    samples = milestone_samples(history, AS_OF)
    return {o.subject_label.split(" · ")[-1]: o for o in predict_project_milestones(rows, samples, AS_OF)}


def test_milestones_follow_recorded_dependencies_only(session):
    design, check = uuid.uuid4(), uuid.uuid4()
    _milestone_history(session, design)
    _milestone_history(session, check)
    project = _open(session)
    a = _ms(session, project, "A", template=design, start=AS_OF, target=AS_OF + timedelta(days=10), sort=1)
    _ms(session, project, "B", template=check, start=AS_OF + timedelta(days=10), target=AS_OF + timedelta(days=20),
        depends=[a.id], sort=2)
    _ms(session, project, "C", template=check, start=AS_OF + timedelta(days=10), target=AS_OF + timedelta(days=20), sort=3)
    loose = _ms(session, project, "Loose", start=AS_OF, target=AS_OF + timedelta(days=5), sort=4)
    _ms(session, project, "D", template=check, start=AS_OF + timedelta(days=10), target=AS_OF + timedelta(days=20),
        depends=[loose.id], sort=5)
    session.commit()
    out = _ms_outcomes(session, project)
    assert out["A"].predicted_date == AS_OF + timedelta(days=14)  # median ratio 1.4 × 10 planned days
    assert out["A"].variance_value == Decimal(4) and out["A"].observed_frequency == Decimal("0.8")
    assert out["B"].predicted_date == AS_OF + timedelta(days=28)  # waits for A (day 14), then 14 days
    assert "Waiting for recorded predecessor" in {f["name"] for f in out["B"].factors}
    # C has no recorded dependency, so the incomplete A does not delay it
    assert out["C"].predicted_date == AS_OF + timedelta(days=24)
    assert out["Loose"].status == INSUFFICIENT and "no template link or stage" in out["Loose"].reason
    assert out["D"].status == INSUFFICIENT and "predecessor(s) without a prediction: Loose" in out["D"].reason


def test_started_milestones_are_conditioned_on_elapsed_time(session):
    design = uuid.uuid4()
    _milestone_history(session, design)
    project = _open(session)
    _ms(session, project, "Running", template=design, start=AS_OF - timedelta(days=13),
        target=AS_OF - timedelta(days=3), actual_start=AS_OF - timedelta(days=13), status=MilestoneStatus.in_progress)
    _ms(session, project, "Undated", template=design, start=AS_OF, sort=2)
    session.commit()
    out = _ms_outcomes(session, project)
    # elapsed 13 days leaves the 14, 16 and 18-day outcomes: fewer than 5, so no prediction
    assert out["Running"].status == INSUFFICIENT and "Already running 13 days" in out["Running"].reason
    assert out["Undated"].status == INSUFFICIENT and "No target date" in out["Undated"].reason


# ----------------------------------------------------------------- resource demand


def _supply(user_id, *, hours_per_day="6", team_id=None, days=120, share=None, name="Designer"):
    start = AS_OF + timedelta(days=1)
    daily, working = {}, set()
    for i in range(days):
        day = start + timedelta(days=i)
        if day.weekday() < 5:
            daily[day] = Decimal(hours_per_day)
            working.add(day)
        else:
            daily[day] = Decimal(0)
    return PersonSupply(user_id, name, team_id, daily, working, share, 12 if share is not None else 0)


def _final(project, value):
    return Outcome(prediction_type="project_final_hours", subject_type="project", subject_key=f"project:{project.id}",
                   subject_label="x", status=PREDICTED, predicted_value=Decimal(value), project_id=project.id)


def test_demand_is_phased_to_the_end_date_and_shortages_are_flagged(session):
    from tests.conftest import IDS

    team = Team(name="Predict team")
    session.add(team)
    session.flush()
    p1 = _open(session, actual="0", due_in=14)
    p2 = _open(session, actual="0", due_in=-5)  # target passed: backlog
    p3 = _open(session, estimate=None)  # no basis for remaining hours
    for p in (p1, p2, p3):
        p.team_id = team.id
    session.commit()
    facts = load_facts(session, [p1, p2, p3], AS_OF)
    supply = {IDS["user_binil"]: _supply(IDS["user_binil"], team_id=team.id, share=Decimal("0.25"))}
    demands, unknown = project_demands(list(facts.values()), {p1.id: _final(p1, "120")}, {}, AS_OF, supply)
    assert [f.project_id for f in unknown] == [p3.id]
    first = next(d for d in demands if d.facts.project_id == p1.id)
    assert first.remaining == Decimal("120") and first.remaining_basis.startswith("predicted final hours")
    assert len(first.daily) == 10 and set(first.daily.values()) == {Decimal(12)}  # 10 weekdays to the target
    backlog = next(d for d in demands if d.facts.project_id == p2.id)
    assert backlog.remaining == Decimal("100") and len(backlog.daily) == BACKLOG_DAYS and "has passed" in backlog.note

    outcomes = build_outcomes(session, AS_OF, demands, unknown, supply, {})
    person = next(o for o in outcomes if o.subject_key == f"person:{IDS['user_binil']}:2w")
    assert person.predicted_value == Decimal("220.00") and person.baseline_value == Decimal("60.00")
    assert person.variance_value == Decimal("160.00") and person.data_used["shortage"] is True
    assert person.data_used["overloaded_weeks"] == ["2025-12-01", "2025-12-08", "2025-12-15"]
    team_2w = next(o for o in outcomes if o.subject_key == f"team:{team.id}:2w")
    assert team_2w.predicted_value == Decimal("220.00")
    assert any("no approved estimate or predicted final hours" in w for w in team_2w.warnings)
    four = next(o for o in outcomes if o.subject_key == f"person:{IDS['user_binil']}:4w")
    assert four.data_used["underutilized"] is False


def test_underutilisation_concentration_and_skill_bottlenecks(session):
    from tests.conftest import IDS

    team = Team(name="Skill team")
    session.add(team)
    session.flush()
    busy = _open(session, actual="0", due_in=28)
    small = _open(session, estimate="10", due_in=28)
    small.designer_id = IDS["user_ranjith"]
    busy.team_id = small.team_id = team.id
    session.commit()
    facts = load_facts(session, [busy, small], AS_OF)
    supply = {
        IDS["user_binil"]: _supply(IDS["user_binil"], team_id=team.id, name="Binil"),
        IDS["user_ranjith"]: _supply(IDS["user_ranjith"], team_id=team.id, name="Ranjith"),
    }
    demands, unknown = project_demands(list(facts.values()), {}, {}, AS_OF, supply)
    skill_id = uuid.uuid4()
    coverage = {busy.id: [{"skill_id": skill_id, "skill_name": "Class A surfacing", "is_mandatory": True,
                           "verified_holder_ids": [IDS["user_ranjith"]]}]}
    outcomes = {o.subject_key: o for o in build_outcomes(session, AS_OF, demands, unknown, supply, coverage)}
    idle = outcomes[f"person:{IDS['user_ranjith']}:4w"]
    assert idle.predicted_value == Decimal("10.00") and idle.data_used["underutilized"] is True
    assert outcomes[f"person:{IDS['user_binil']}:4w"].data_used["underutilized"] is False
    team_4w = outcomes[f"team:{team.id}:4w"]
    assert team_4w.data_used["single_person_dependency"] is True
    skill = outcomes[f"skill:{skill_id}:2w"]
    assert skill.data_used["single_person_dependency"] is True and skill.baseline_value == Decimal("60.00")
    assert skill.data_used["projects"][0]["designer_is_verified"] is False


def test_demand_without_any_estimate_is_not_reported_as_idle(session):
    from tests.conftest import IDS

    team = Team(name="Unestimated team")
    session.add(team)
    session.flush()
    bare = _open(session, estimate=None)
    bare.team_id = team.id
    session.commit()
    facts = load_facts(session, [bare], AS_OF)
    supply = {IDS["user_binil"]: _supply(IDS["user_binil"], team_id=team.id)}
    demands, unknown = project_demands(list(facts.values()), {}, {}, AS_OF, supply)
    outcomes = {o.subject_key: o for o in build_outcomes(session, AS_OF, demands, unknown, supply, {})}
    person = outcomes[f"person:{IDS['user_binil']}:4w"]
    assert person.status == INSUFFICIENT and person.predicted_value is None
    assert "None of this person's 1 open project(s)" in person.reason
    assert outcomes[f"team:{team.id}:4w"].status == INSUFFICIENT


def test_capacity_check_can_only_move_delivery_later(session):
    history = _history(session, ["120"] * 5, durations=[50, 60, 70, 80, 90])
    project = _open(session, started_days_ago=30)
    session.commit()
    facts = _facts(session, project)
    samples = duration_samples(_history_facts(session, history))
    base = predict_delivery(facts, samples, AS_OF)
    later = CapacityCheck(base.predicted_date + timedelta(days=9), Decimal("90"), "Binil is fully booked.")
    bound = predict_delivery(facts, samples, AS_OF, capacity=later)
    assert bound.predicted_date == later.finish and bound.lower_date is None and bound.observed_frequency is None
    assert {f["name"]: f["role"] for f in bound.factors}["Designer capacity"] == "calculation"
    earlier = CapacityCheck(base.predicted_date - timedelta(days=20), Decimal("90"), "Plenty of time.")
    free = predict_delivery(facts, samples, AS_OF, capacity=earlier)
    assert free.predicted_date == base.predicted_date
    assert {f["name"]: f["role"] for f in free.factors}["Designer capacity"] == "context"


def test_capacity_finish_respects_other_work():
    from app.services.predictive.resources import capacity_finish

    person = _supply(uuid.uuid4())  # 6 h per weekday
    first = min(d for d in person.working_days)
    assert capacity_finish(person, {}, Decimal("12"), AS_OF) == sorted(person.working_days)[1]
    other = {d: Decimal(6) for d in sorted(person.working_days)[:5]}  # first week fully booked
    assert capacity_finish(person, other, Decimal("6"), AS_OF) == sorted(person.working_days)[5]
    assert capacity_finish(person, {}, Decimal("100000"), AS_OF) is None
    assert first > AS_OF


def test_non_project_share_needs_four_weeks(session):
    from tests.conftest import IDS

    for week in range(4):
        _book(session, None, "10", week_offset=week)
        _book(session, _open(session).id, "30", week_offset=week)
    session.commit()
    shares = non_project_shares(session, [IDS["user_binil"], IDS["user_ranjith"]], date(2025, 2, 2))
    assert shares[IDS["user_binil"]] == (Decimal("0.2500"), 4)
    assert shares[IDS["user_ranjith"]] == (None, 0)


def test_person_demand_is_scored_against_booked_project_hours(session):
    from tests.conftest import IDS

    project = _open(session)
    _book(session, project.id, "24", week_offset=1)  # 2025-01-13 … 15
    row = Prediction(
        prediction_type="resource_demand", model_version="demand-1", subject_type="person",
        subject_key=f"person:{IDS['user_binil']}:2w", subject_label="Binil — next 2 weeks",
        as_of=date(2025, 1, 5), horizon_start=date(2025, 1, 6), horizon_end=date(2025, 1, 19),
        status=PREDICTED, predicted_value=Decimal("30"), unit="hours",
    )
    skill = Prediction(
        prediction_type="resource_demand", model_version="demand-1", subject_type="skill",
        subject_key="skill:x:2w", subject_label="Skill", as_of=date(2025, 1, 5), horizon_start=date(2025, 1, 6),
        horizon_end=date(2025, 1, 19), status=PREDICTED, predicted_value=Decimal("30"), unit="hours",
    )
    session.add_all([row, skill])
    session.commit()
    evaluate_outcomes(session, date(2025, 1, 19))
    assert row.outcome_status == OUTCOME_PENDING  # horizon not over yet
    evaluate_outcomes(session, date(2025, 1, 20))
    assert row.outcome_status == OUTCOME_EVALUATED and row.actual_value == Decimal("24.00")
    assert row.error_value == Decimal("6.00") and row.pct_error == Decimal("25.00")
    assert skill.outcome_status == OUTCOME_NOT_EVALUABLE


# ----------------------------------------------------------------- finance

FIN_AS_OF = date(2030, 3, 15)


def _paid_history(session, team, delays=(10, 12, 14, 16, 18)):
    for i, delay in enumerate(delays):
        quote = _quote(session, team, awarded="100")
        due = date(2029, 6, 1) + timedelta(days=20 * i)
        _invoice(session, quote, "100", due - timedelta(days=30), due)
        session.add(QuotePaymentLine(quote_id=quote.id, amount=Decimal("100"), line_date=due + timedelta(days=delay)))
    session.flush()


def _fin_inputs(session, as_of=FIN_AS_OF):
    forecast = build_finance_forecast(session, as_of=as_of)
    ledgers = load_ledgers(session)
    return forecast, ledgers


def _period(outcomes, key):
    return next(o for o in outcomes if o.subject_key == key)


def test_collections_move_due_dates_by_payment_history(session):
    team = _finance_team(session)
    _paid_history(session, team)
    upcoming = _quote(session, team, awarded="500")
    _invoice(session, upcoming, "500", date(2030, 2, 25), date(2030, 3, 25))
    late = _quote(session, team, awarded="300")
    _invoice(session, late, "300", date(2030, 2, 8), date(2030, 3, 10))  # 5 days overdue
    very_late = _quote(session, team, awarded="200")
    _invoice(session, very_late, "200", date(2030, 2, 1), date(2030, 3, 2))  # 13 days overdue
    undated = _quote(session, team, awarded="50")
    _invoice(session, undated, "50", date(2030, 3, 1), None)
    session.commit()
    forecast, ledgers = _fin_inputs(session)
    delays = payment_delays(ledgers, FIN_AS_OF)
    assert sorted(d for _, d in delays) == [10, 12, 14, 16, 18]
    outcomes = predict_collections(forecast, delays, FIN_AS_OF)
    march, april = _period(outcomes, "INR:2030-03"), _period(outcomes, "INR:2030-04")
    assert march.predicted_value == Decimal("300.00")  # 5 days overdue + median 14-day delay → 24 March
    assert march.baseline_value == Decimal("500.00")  # contractual: the 25 March invoice
    assert april.predicted_value == Decimal("500.00") and april.baseline_value == Decimal("0.00")
    item = april.data_used["items"][0]
    assert item["expected"] == "2030-04-08" and item["median_delay_days"] == 14 and item["basis"] == "this customer's 5 cases"
    reasons = {i["invoice"] or i["amount"]: i["reason"] for i in april.data_used["not_dated"]}
    assert any("history too small" in r for r in reasons.values())  # 13 days overdue: only 3 longer delays
    assert any("no due date" in r for r in reasons.values())
    assert april.data_used["ledger_totals"]["outstanding"] == "1050.00"
    assert any("cannot be dated" in w for w in april.warnings)


def test_collections_without_payment_history_are_insufficient(session):
    team = _finance_team(session)
    quote = _quote(session, team, awarded="500")
    _invoice(session, quote, "500", date(2030, 2, 25), date(2030, 3, 25))
    session.commit()
    forecast, ledgers = _fin_inputs(session)
    outcomes = predict_collections(forecast, payment_delays(ledgers, FIN_AS_OF), FIN_AS_OF)
    assert outcomes and all(o.status == INSUFFICIENT for o in outcomes)
    assert "Payment history too small (0 comparable case(s); 5 needed)" in outcomes[0].reason


def test_billing_needs_completion_and_invoicing_history(session):
    team = _finance_team(session)
    for i, lag in enumerate((5, 6, 7, 8, 9)):
        done = _project(session, team_id=team.id, status=ExecutionStatus.completed,
                        completed_at=datetime(2029, 9, 1 + i, 12))
        quote = _quote(session, team, awarded="100", project_id=done.id)
        milestone = _fin_milestone(session, quote, 1, "100", "PROJECT_COMPLETION")
        _invoice(session, quote, "100", date(2029, 9, 1 + i) + timedelta(days=lag), None, payment_milestone_id=milestone.id)
    open_project = _project(session, team_id=team.id)
    quote = _quote(session, team, awarded="1000", project_id=open_project.id)
    _fin_milestone(session, quote, 1, "60", "PROJECT_COMPLETION")
    _fin_milestone(session, quote, 2, "40", "DESIGN_MILESTONE", status="READY_TO_INVOICE")
    finished = _project(session, team_id=team.id, status=ExecutionStatus.completed, completed_at=datetime(2030, 3, 12, 9))
    waiting = _quote(session, team, awarded="200", project_id=finished.id)
    _fin_milestone(session, waiting, 1, "100", "PROJECT_COMPLETION")
    unpredicted = _project(session, team_id=team.id)
    other = _quote(session, team, awarded="300", project_id=unpredicted.id)
    _fin_milestone(session, other, 1, "100", "PROJECT_COMPLETION")
    session.commit()

    forecast, ledgers = _fin_inputs(session)
    lags = invoice_lags(ledgers, FIN_AS_OF)
    assert sorted(v for _, v in lags) == [5, 6, 7, 8, 9]
    predicted = Outcome(prediction_type="project_delivery", subject_type="project", subject_key="p", subject_label="p",
                        status=PREDICTED, predicted_date=date(2030, 4, 20), project_id=open_project.id)
    completions = completions_for(ledgers, {open_project.id: predicted})
    customers = {ledger.quote.id: ledger.quote.customer_id for ledger in ledgers}
    outcomes = predict_billing(forecast, lags, FIN_AS_OF, completions, customers)
    march, april = _period(outcomes, "INR:2030-03"), _period(outcomes, "INR:2030-04")
    assert march.predicted_value == Decimal("200.00")  # completed 12 March, waiting 3 days; median lag 7 → 19 March
    assert april.predicted_value == Decimal("600.00")  # predicted completion 20 April + 7 days
    assert april.baseline_value == Decimal("0.00")  # Phase 3 could not date it: the project has no future target
    assert april.data_used["items"][0]["completion_basis"] == "predicted completion"
    assert april.data_used["ready_to_invoice"] == "400.00"
    assert any("no completion prediction" in i["reason"] for i in april.data_used["not_dated"])

    no_history = predict_billing(forecast, [], FIN_AS_OF, completions, customers)
    assert all(o.status == INSUFFICIENT for o in no_history)
    assert "history too small" in no_history[0].reason


def test_finance_predictions_are_scored_like_for_like(session):
    team = _finance_team(session)
    _paid_history(session, team)
    quote = _quote(session, team, awarded="500")
    line = _invoice(session, quote, "500", date(2030, 2, 25), date(2030, 3, 25))
    session.commit()
    engine.run_predictions(session, as_of=FIN_AS_OF)
    april = session.scalar(select(Prediction).where(Prediction.prediction_type == "finance_collections",
                                                   Prediction.subject_key == "INR:2030-04"))
    assert april.predicted_value == Decimal("500.00") and str(line.id) in json.loads(april.data_used_json)["population"]
    session.add(QuotePaymentLine(quote_id=quote.id, amount=Decimal("400"), line_date=date(2030, 4, 10)))
    later = _quote(session, team, awarded="900")  # issued after the prediction: not part of the comparison
    _invoice(session, later, "900", date(2030, 4, 1), date(2030, 4, 5))
    session.add(QuotePaymentLine(quote_id=later.id, amount=Decimal("900"), line_date=date(2030, 4, 6)))
    session.commit()
    evaluate_outcomes(session, date(2030, 5, 1))
    session.refresh(april)
    assert april.outcome_status == OUTCOME_EVALUATED and april.actual_value == Decimal("400.00")
    assert april.error_value == Decimal("100.00") and april.naive_abs_error == Decimal("400.00")


# ----------------------------------------------------------------- portfolio patterns


def _pattern_facts(base, n, *, ratio, customer, complexity="medium", slip=0):
    out = []
    for i in range(n):
        done = date(2025, 1, 1) + timedelta(days=i)
        out.append(base.with_changes(
            project_id=uuid.uuid4(), customer_id=customer, customer_name=str(customer)[:4], complexity=complexity,
            estimate_approved=True, original_estimate=Decimal("100"), actual_status="recorded",
            actual_hours=Decimal(str(100 * ratio + i * 0.1)), completed_on=done, committed_date=done - timedelta(days=slip),
        ))
    return out


def test_patterns_need_size_and_significance_and_respect_strata(session):
    base = _facts(session, _open(session))
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    history = (_pattern_facts(base, 10, ratio=1.5, customer=a) + _pattern_facts(base, 10, ratio=1.0, customer=b)
               + _pattern_facts(base, 4, ratio=2.0, customer=c))
    result = project_patterns(history, {})
    customer_rows = [r for r in result["patterns"] if r["dimension"] == "customer" and r["metric"] == "effort_ratio"]
    assert [r["group_label"] for r in customer_rows] == [str(b)[:4]]
    row = customer_rows[0]
    assert row["n"] == 10 and row["comparison_n"] == 14 and row["p_value"] < 0.05
    assert row["stratum"] == "No project type, medium complexity" and row["finding"].startswith(str(b)[:4])
    # A sits between B and C, so against everyone else its difference is not reliable (p ≈ 0.08)
    middle = next(r for r in result["no_reliable_difference"] if r["group_label"] == str(a)[:4] and r["metric"] == "effort_ratio")
    assert middle["p_value"] >= 0.05 and middle["finding"] is None
    small = next(r for r in result["too_small"] if r["group_label"] == str(c)[:4] and r["metric"] == "effort_ratio")
    assert small == {"metric": "effort_ratio", "dimension": "customer", "group_label": str(c)[:4],
                     "stratum": "No project type, medium complexity", "n": 4, "comparison_n": 20}
    assert not any(r["group_label"] == str(c)[:4] for r in result["patterns"] + result["no_reliable_difference"])

    # Customers that differ only because their projects differ in complexity are never compared with each other.
    split = _pattern_facts(base, 10, ratio=1.5, customer=a, complexity="high") + _pattern_facts(base, 10, ratio=1.0, customer=b, complexity="low")
    result = project_patterns(split, {})
    assert not [r for r in result["patterns"] + result["no_reliable_difference"] if r["dimension"] == "customer"]
    assert any(r["dimension"] == "complexity" for r in result["patterns"])


def test_patterns_report_no_difference_without_significance(session):
    base = _facts(session, _open(session))
    a, b = uuid.uuid4(), uuid.uuid4()
    history = _pattern_facts(base, 9, ratio=1.2, customer=a) + _pattern_facts(base, 9, ratio=1.2, customer=b)
    result = project_patterns(history, {})
    assert not [r for r in result["patterns"] if r["dimension"] == "customer"]
    rows = [r for r in result["no_reliable_difference"] if r["dimension"] == "customer" and r["metric"] == "effort_ratio"]
    assert rows and all(r["finding"] is None and r["significant"] is False for r in rows)


# ----------------------------------------------------------------- Stage 5: predictive Control Tower


def _stored(session, project, ptype, *, variance="30", baseline="100", as_of=AS_OF, shadow=False,
            milestone=None, **extra) -> Prediction:
    """A stored prediction row standing in for model output."""
    days = ptype in ("project_delivery", "milestone_delay")
    values = dict(
        unit="days" if days else "hours", baseline_value=None if days else Decimal(baseline),
        predicted_value=None if days else Decimal(baseline) + Decimal(variance),
        predicted_date=AS_OF + timedelta(days=60 + int(variance)) if days else None,
        baseline_date=AS_OF + timedelta(days=60) if days else None,
        subject_type="milestone" if milestone else "project", subject_key=f"x:{uuid.uuid4()}", subject_label="Subject",
    )
    values.update(extra)
    row = Prediction(
        prediction_type=ptype, model_version=registry.TYPES[ptype].versions[0].version, is_shadow=shadow,
        project_id=project.id if project else None, milestone_id=milestone, as_of=as_of, status=PREDICTED,
        baseline_label="Current baseline", variance_value=Decimal(variance), sample_size=5,
        comparison_group="5 completed projects", **values,
    )
    session.add(row)
    session.flush()
    return row


def test_forecast_findings_are_separate_and_explain_the_forecast(session):
    from app.models.control_tower import ProjectRiskFinding
    from app.services import control_tower_service as ct

    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    project = _open(session, actual="40", started_days_ago=30, due_in=20)
    session.commit()
    before = (project.due_date, project.forecast_completion_date)
    estimates = [(e.original_hours, e.current_hours) for e in session.scalars(select(ProjectStageEstimate))]
    engine.run_predictions(session, as_of=AS_OF)
    ct.run_evaluation(session, today=AS_OF)

    rows = {f.rule_id: f for f in session.scalars(select(ProjectRiskFinding).where(
        ProjectRiskFinding.project_id == project.id, ProjectRiskFinding.source == "predictive"))}
    assert set(rows) == {"estimate_overrun_forecast", "delivery_forecast_risk"}
    overrun = rows["estimate_overrun_forecast"]
    assert overrun.severity == "high" and overrun.category == "effort"
    assert overrun.prediction_id == _latest(session, "project_final_hours", project.id).id
    assert "not a certainty" in overrun.explanation and "30%" in overrun.title
    labels = {line["label"] for line in json.loads(overrun.evidence_json)}
    assert {"Forecast", "Likely range", "Current approved estimate", "Comparable history", "Model"} <= labels
    assert rows["delivery_forecast_risk"].category == "delivery"

    scope = ct.FindingScope()
    risks, _ = ct.list_findings(session, scope, ct.FindingQuery(view="risks", project_id=project.id), page=1, page_size=50)
    forecasts, _ = ct.list_findings(session, scope, ct.FindingQuery(view="predictive", project_id=project.id), page=1, page_size=50)
    assert all(f.source == "operational" for f in risks)
    assert {f.rule_id for f in forecasts} == set(rows) and all(f.source_label == "Predictive" for f in forecasts)
    summary = ct.build_summary(session, scope, AS_OF)
    assert summary.open_predictive == 2

    session.refresh(project)
    assert (project.due_date, project.forecast_completion_date) == before
    assert [(e.original_hours, e.current_hours) for e in session.scalars(select(ProjectStageEstimate))] == estimates


def test_forecasts_defer_to_operational_findings_and_skip_stale_shadow_or_disabled(session):
    from app.services import control_tower_service as ct

    registry.sync(session)
    over = _open(session, actual="120")            # already over its estimate: operational finding instead
    fresh = _open(session, actual="40")
    stale = _open(session, actual="40")
    shadow = _open(session, actual="40")
    small = _open(session, actual="40")
    late_ms = _ms(session, fresh, "Late", target=AS_OF - timedelta(days=3), start=AS_OF - timedelta(days=20))
    for project in (over, fresh):
        _stored(session, project, "project_final_hours")
    _stored(session, stale, "project_final_hours", as_of=AS_OF - timedelta(days=9))
    _stored(session, shadow, "project_final_hours", shadow=True)
    _stored(session, small, "project_final_hours", variance="5")
    _stored(session, fresh, "milestone_delay", variance="10", milestone=late_ms.id)
    _stored(session, fresh, "project_delivery", variance="20")
    session.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == "project_delivery")).is_enabled = False
    session.commit()

    _, detections = ct.detect_all(session, AS_OF)
    predictive = {(d.rule_id, d.project_id) for d in detections if d.source == "predictive"}
    assert predictive == {("estimate_overrun_forecast", fresh.id)}
    operational = {(d.rule_id, d.project_id, d.milestone_id) for d in detections if d.source == "operational"}
    assert ("estimate_overrun_realized", over.id, None) in operational
    assert ("milestone_overdue", fresh.id, late_ms.id) in operational


def test_resource_bottleneck_is_raised_once_without_naming_the_designer(session):
    from app.services import control_tower_service as ct

    registry.sync(session)
    first, second = _open(session, due_in=10), _open(session, due_in=40)
    projects = [{"project_id": str(p.id), "end": (AS_OF + timedelta(days=d)).isoformat()} for p, d in ((second, 40), (first, 10))]
    for key, complete in (("person:a:4w", True), ("person:a:2w", True), ("person:b:4w", False)):
        _stored(session, None, "resource_demand", variance="0", subject_type="person", subject_key=key,
                subject_label="Jane Doe — next 4 weeks", predicted_value=Decimal("192"), baseline_value=Decimal("120"),
                data_used_json=json.dumps({"projects": projects, "shortage": True, "demand_complete": complete,
                                           "utilisation_percent": "160.0", "overloaded_weeks": ["2025-12-01"]}))
    session.commit()

    _, detections = ct.detect_all(session, AS_OF)
    [finding] = [d for d in detections if d.rule_id == "resource_bottleneck"]
    assert finding.project_id == first.id and finding.severity == "high" and finding.rule.category == "resource"
    text = " ".join([finding.title, finding.explanation] + [f"{k} {v}" for k, v in finding.evidence])
    assert "Jane" not in text and "evenly" in finding.explanation


def test_triage_and_convert_never_change_the_condition_or_records(client, session):
    from app.models.models import Activity
    from app.models.assistant import AIRecommendation
    from app.models.control_tower import ProjectRiskFinding
    from app.models.enums import ActivityAction
    from app.services import control_tower_service as ct
    from tests.test_control_tower import _scoped_user
    from tests.conftest import login

    registry.sync(session)
    project = _open(session, actual="40")
    _stored(session, project, "project_final_hours")
    session.commit()
    ct.run_evaluation(session, today=AS_OF)
    finding = session.scalar(select(ProjectRiskFinding).where(ProjectRiskFinding.project_id == project.id,
                                                              ProjectRiskFinding.source == "predictive"))
    url = f"/api/v1/control-tower/findings/{finding.id}"
    headers = client.auth_headers
    listing = "/api/v1/control-tower"

    assert client.post(f"{url}/triage", json={"action": "dismiss"}, headers=headers).status_code == 409
    body = client.post(f"{url}/triage", json={"action": "investigate", "note": "Checking scope"}, headers=headers).json()
    assert body["triage_status"] == "investigating" and body["triaged_by_name"] and body["status"] == "active"
    assert client.post(f"{url}/triage", json={"action": "dismiss", "note": "Known extra scope"}, headers=headers).status_code == 200

    params = {"project_id": str(project.id), "view": "predictive"}
    assert client.get(listing, params=params, headers=headers).json()["total"] == 0
    hidden = client.get(listing, params={**params, "triage": "dismissed"}, headers=headers).json()
    assert hidden["total"] == 1 and hidden["summary"]["dismissed"] >= 1
    ct.run_evaluation(session, today=AS_OF)
    session.refresh(finding)
    assert finding.status == "active" and finding.triage_status == "dismissed"

    converted = client.post(f"{url}/convert", json={"note": "Raise at weekly review"}, headers=headers)
    assert converted.status_code == 200, converted.text
    rec = session.get(AIRecommendation, uuid.UUID(converted.json()["recommendation_id"]))
    assert rec.module == "control_tower" and rec.status == "new" and rec.project_id == project.id
    assert rec.suggested_action == finding.recommended_action
    assert {s["type"] for s in json.loads(rec.evidence_json)["sources"]} == {"control_tower_finding", "prediction"}
    again = client.post(f"{url}/convert", json={}, headers=headers).json()
    assert again["recommendation_id"] == str(rec.id)
    reopened = client.post(f"{url}/triage", json={"action": "reopen"}, headers=headers).json()
    assert reopened["triage_status"] is None and reopened["recommendation_id"] == str(rec.id)
    events = [e["event"] for e in reopened["events"]]
    assert {"investigating", "dismissed", "converted", "triage_cleared"} <= set(events)
    audits = session.scalars(select(Activity).where(Activity.action == ActivityAction.risk_finding_triaged)).all()
    assert len(audits) == 4

    _scoped_user(session, modules='["dashboard", "projects", "timesheets", "reports"]')
    other = login(client, "binil@prosohm.com")
    assert client.post(f"{url}/triage", json={"action": "investigate"}, headers=other).status_code == 403
    assert client.post(f"{url}/convert", json={}, headers=other).status_code == 403
    session.refresh(project)
    assert project.due_date == AS_OF + timedelta(days=60)


# ----------------------------------------------------------------- Stage 6: scenarios and assistant


def test_scenarios_are_isolated_hypothetical_and_audited(session):
    from app.models.models import Activity, User
    from app.models.prediction import PredictionScenario
    from app.services.predictive.scenarios import (
        HYPOTHETICAL_LABEL, Assumptions, ScenarioError, delete_scenario, evaluate_scenario, project_scenarios,
        save_scenario,
    )
    from tests.conftest import IDS

    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    project = _open(session, actual="40", started_days_ago=30, due_in=20)
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    stored = _latest(session, "project_final_hours", project.id)
    predictions_before = session.scalar(select(func.count(Prediction.id)))
    before = (project.due_date, project.designer_id, project.forecast_completion_date)
    own = select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == project.id)
    estimates = [(e.original_hours, e.current_hours) for e in session.scalars(own)]

    result = evaluate_scenario(session, project, Assumptions(scope_change_percent=Decimal(20), extra_delay_days=10,
                                                             target_shift_days=14), as_of=AS_OF)
    assert result["label"] == HYPOTHETICAL_LABEL
    assert Decimal(result["baseline"]["final_hours"]["predicted_value"]) == stored.predicted_value
    assert Decimal(result["scenario"]["final_hours"]["predicted_value"]) > stored.predicted_value
    shifted = date.fromisoformat(result["scenario"]["delivery"]["baseline_date"])
    assert shifted == date.fromisoformat(result["baseline"]["delivery"]["baseline_date"]) + timedelta(days=14)
    factors = {f["name"] for f in result["scenario"]["delivery"]["factors"]}
    assert {"Scope change (scenario)", "Added delay (scenario)"} <= factors
    rows = {r["measure"]: r for r in result["comparison"]}
    assert rows["Predicted final hours"]["difference"].startswith("+")
    assert "Target date compared against" in rows

    anurag = session.get(User, IDS["user_anurag"])
    pm = session.get(User, IDS["user_pm"])
    saved = save_scenario(session, project, name="Scope +20%", assumptions=Assumptions(scope_change_percent=Decimal(20)),
                          user=anurag)
    assert saved.created_by_id == anurag.id and saved.updated_by_id is None
    saved = save_scenario(session, project, name="Scope +30%", assumptions=Assumptions(scope_change_percent=Decimal(30)),
                          user=pm, scenario=saved)
    assert saved.updated_by_id == pm.id and json.loads(saved.assumptions_json)["scope_change_percent"] == "30"
    assert json.loads(saved.result_json)["label"] == HYPOTHETICAL_LABEL
    delete_scenario(session, saved, user=pm)
    assert project_scenarios(session, project.id) == [] and session.get(PredictionScenario, saved.id).is_deleted
    actions = {a.action.value for a in session.scalars(select(Activity).where(Activity.entity_id == saved.id))}
    assert actions == {"prediction_scenario_saved", "prediction_scenario_deleted"}

    with pytest.raises(ScenarioError):
        save_scenario(session, project, name="Nothing", assumptions=Assumptions(), user=anurag)
    with pytest.raises(ScenarioError):
        evaluate_scenario(session, project, Assumptions(milestone_delays={str(uuid.uuid4()): 5}), as_of=AS_OF)
    with pytest.raises(ScenarioError):
        evaluate_scenario(session, project, Assumptions(designer_id=uuid.uuid4()), as_of=AS_OF)
    closed = _history(session, ["100"], prefix="CL")[0]
    with pytest.raises(ScenarioError):
        evaluate_scenario(session, closed, Assumptions(extra_delay_days=5), as_of=AS_OF)

    session.expire_all()
    assert session.scalar(select(func.count(Prediction.id))) == predictions_before
    project = session.get(Project, project.id)
    assert (project.due_date, project.designer_id, project.forecast_completion_date) == before
    assert [(e.original_hours, e.current_hours) for e in session.scalars(own)] == estimates


def test_assistant_reads_stored_predictions_and_respects_permissions(client, session, monkeypatch):
    from app.api.v1.assistant import reset_rate_limits
    from app.core import config
    from app.services.assistant.provider import set_provider_override
    from tests.conftest import login
    from tests.test_ai_assistant import ScriptedProvider, _ask, call
    from tests.test_control_tower import _scoped_user

    reset_rate_limits()
    monkeypatch.setattr(config, "AI_ASSISTANT_ENABLED", True)
    monkeypatch.setattr(config, "AI_PROVIDER", "heuristic")
    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    project = _open(session, actual="40", started_days_ago=30, due_in=20)
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    ref = project.code or project.tool_number
    try:
        provider = ScriptedProvider([
            {"tool_calls": [call("list_project_predictions", {"type": "final_hours"}, "a"),
                            call("explain_project_prediction", {"project": ref}, "b"),
                            call("run_what_if_scenario", {"project": ref, "scope_change_percent": 25}, "c")]},
            {"content": "Forecasts summarised."},
        ])
        set_provider_override(provider)
        answer = _ask(client, client.auth_headers, "Which projects are likely to exceed approved hours?")
        listed, explained, scenario = provider.tool_payloads()
        top = listed["data"]["predictions"][0]
        assert top["forecast"] == "130.00 h" and top["comparable_cases"] == 5 and top["variance"] == "30.00"
        assert any("not certainties" in note for note in listed["limitations"])
        assert any("out of date" in note for note in listed["limitations"])  # AS_OF is long before today
        factors = {f["name"] for p in explained["data"]["predictions"] for f in p.get("factors", [])}
        assert "Comparable projects" in factors
        assert scenario["data"]["label"].startswith("Hypothetical")
        assert any(s["kind"] == "forecast" for s in answer["sources"])
        assert "never compute" in provider.requests[0]["messages"][0]["content"]

        _scoped_user(session, modules='["dashboard", "projects", "timesheets"]')
        provider = ScriptedProvider([{"content": "ok"}])
        set_provider_override(provider)
        _ask(client, login(client, "binil@prosohm.com"), "Resource bottlenecks?")
        offered = set(provider.requests[0]["tools"])
        assert "list_project_predictions" in offered
        assert not offered & {"get_resource_demand_forecast", "get_finance_timing_forecast", "get_historical_patterns",
                              "run_what_if_scenario"}
    finally:
        set_provider_override(None)
        reset_rate_limits()


# ----------------------------------------------------------------- Stage 7: accuracy, governance, API


def _scored_rows(session, n, *, version="hours-1", shadow=False, error="10", naive="15", evaluated_days_ago=10,
                 horizon=20, observed=None, event=None, ranged=False):
    """Stored predictions already scored against an outcome (mocked model output)."""
    now = datetime.utcnow()
    for i in range(n):
        session.add(Prediction(
            prediction_type="project_final_hours", model_version=version, is_shadow=shadow, subject_type="project",
            subject_key=f"s:{uuid.uuid4()}", subject_label=f"P{i}", as_of=AS_OF, status=PREDICTED, unit="hours",
            predicted_value=Decimal("110"), baseline_value=Decimal("100"), variance_value=Decimal("10"),
            lower_value=Decimal("95") if ranged else None, upper_value=Decimal("130") if ranged else None,
            sample_size=10, is_latest=False, counts_for_accuracy=True, outcome_status=OUTCOME_EVALUATED,
            actual_value=Decimal("100"), error_value=Decimal(error), abs_error=Decimal(error),
            pct_error=Decimal(error), naive_abs_error=Decimal(naive) if naive else None, horizon_days=horizon,
            observed_frequency=Decimal(str(observed)) if observed is not None else None, event_occurred=event,
            evaluated_at=now - timedelta(days=evaluated_days_ago),
        ))
    session.flush()


def test_accuracy_needs_enough_scored_predictions_and_detects_degradation(session):
    from app.services.predictive.accuracy import MIN_EVALUATED, accuracy_report

    registry.sync(session)
    _scored_rows(session, MIN_EVALUATED - 1)
    [report] = accuracy_report(session, ["project_final_hours"])
    assert report["overall"]["evaluated"] == MIN_EVALUATED - 1 and not report["overall"]["reportable"]
    assert "mean_absolute_error" not in report["overall"]

    _scored_rows(session, 1, ranged=True)
    _scored_rows(session, MIN_EVALUATED, error="30", evaluated_days_ago=200, horizon=120, observed=0.6, event=True,
                 ranged=True)
    [report] = accuracy_report(session, ["project_final_hours"])
    overall = report["overall"]
    assert overall["evaluated"] == 2 * MIN_EVALUATED and overall["mean_absolute_error"] == 20.0
    assert overall["naive_baseline"]["baseline_mae"] == 15.0 and overall["naive_baseline"]["better_than_baseline"] is False
    assert overall["range_coverage"]["n"] == MIN_EVALUATED + 1
    horizons = {h["horizon"]: h for h in report["by_horizon"]}
    assert horizons["0–30 days"]["mean_absolute_error"] == 10.0 and horizons["91–180 days"]["mean_absolute_error"] == 30.0
    band = next(b for b in report["calibration"] if b["band"] == "50%–75%")
    assert band["n"] == MIN_EVALUATED and band["event_rate"] == 1.0
    assert report["degradation"]["status"] == "stable"  # recent error (10) is lower than earlier (30)

    _scored_rows(session, MIN_EVALUATED, error="100", evaluated_days_ago=5)
    [report] = accuracy_report(session, ["project_final_hours"])
    assert report["degradation"]["status"] == "degraded"


def test_a_worse_model_is_never_activated_and_changes_are_audited(session):
    from app.models.models import Activity, User
    from app.services.predictive.accuracy import GovernanceError, MIN_EVALUATED, activate_version, set_enabled
    from tests.conftest import IDS

    admin = session.get(User, IDS["user_anurag"])
    registry.register_version("project_final_hours", registry.ModelSpec("hours-2", "Candidate."))
    registry.sync(session)
    _scored_rows(session, 2)
    _scored_rows(session, 2, version="hours-2", shadow=True, error="5")
    with pytest.raises(GovernanceError, match="justification"):
        activate_version(session, "project_final_hours", "hours-2", user=admin, note=None)

    _scored_rows(session, MIN_EVALUATED)
    _scored_rows(session, MIN_EVALUATED, version="hours-2", shadow=True, error="25")
    with pytest.raises(GovernanceError, match="Refused"):
        activate_version(session, "project_final_hours", "hours-2", user=admin, note="Trying anyway with a note")
    setting = session.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == "project_final_hours"))
    assert setting.active_version == "hours-1"

    _scored_rows(session, 3 * MIN_EVALUATED, version="hours-2", shadow=True, error="1")
    target = activate_version(session, "project_final_hours", "hours-2", user=admin, note=None)
    assert target.status == MODEL_ACTIVE and setting.active_version == "hours-2"
    statuses = {v.version: v.status for v in session.scalars(select(PredictionModelVersion).where(
        PredictionModelVersion.prediction_type == "project_final_hours"))}
    assert statuses == {"hours-1": MODEL_CANDIDATE, "hours-2": MODEL_ACTIVE}

    with pytest.raises(GovernanceError):
        set_enabled(session, "project_delivery", False, user=admin, reason="  ")
    set_enabled(session, "project_delivery", False, user=admin, reason="Under review")
    actions = [a.action.value for a in session.scalars(select(Activity).where(
        Activity.action.in_(["prediction_model_activated", "prediction_setting_changed"])))]
    assert sorted(actions) == ["prediction_model_activated", "prediction_setting_changed"]


def test_predictions_api_enforces_permissions_and_separates_actuals(client, session):
    from app.models.prediction import PredictionScenario
    from tests.conftest import login
    from tests.test_control_tower import _scoped_user
    from tests.test_engineering_metrics import _project as _plain_project

    _history(session, ["110", "120", "130", "140", "150"], durations=[50, 60, 70, 80, 90])
    mine = _open(session, actual="40", started_days_ago=30, due_in=20)
    hidden = _plain_project(session, code="PR-HIDDEN", quoted="300")
    hidden.designer_id, hidden.design_leader_id = uuid.uuid4(), uuid.uuid4()
    session.commit()
    engine.run_predictions(session, as_of=AS_OF)
    _stored(session, hidden, "project_final_hours")
    session.commit()
    base = "/api/v1/predictions"
    admin = client.auth_headers

    overview = client.get(f"{base}/overview", headers=admin).json()
    assert overview["can"]["manage_models"] is True and overview["freshness"]["last_run_as_of"] == AS_OF.isoformat()
    assert any(r["project_id"] == str(mine.id) for r in overview["likely_overrun"])
    assert overview["coverage"]["project_final_hours"]["predicted"] >= 1

    detail = client.get(f"{base}/projects/{mine.id}", headers=admin).json()
    assert detail["recorded"]["current_estimate"] == "100.00" and detail["final_hours"]["predicted_value"] == "130.00"
    assert detail["final_hours"]["baseline_label"] and detail["history"]["project_final_hours"]

    preview = client.post(f"{base}/projects/{mine.id}/scenarios/preview", json={"scope_change_percent": 20}, headers=admin)
    assert preview.status_code == 200 and preview.json()["label"].startswith("Hypothetical")
    assert session.scalar(select(func.count(PredictionScenario.id))) == 0
    created = client.post(f"{base}/projects/{mine.id}/scenarios",
                          json={"name": "Scope +20%", "assumptions": {"scope_change_percent": 20}}, headers=admin)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert created.json()["created_by"]
    assert client.put(f"{base}/scenarios/{sid}", json={"name": "Scope +25%", "assumptions": {"scope_change_percent": 25}},
                      headers=admin).json()["updated_by"]
    assert len(client.get(f"{base}/projects/{mine.id}/scenarios", headers=admin).json()["scenarios"]) == 1
    assert client.post(f"{base}/projects/{mine.id}/scenarios/preview", json={"extra_delay_days": 999},
                       headers=admin).status_code == 422

    _scoped_user(session, modules='["dashboard", "projects", "timesheets"]')
    designer = login(client, "binil@prosohm.com")
    assert client.get(f"{base}/overview", headers=designer).status_code == 403

    _scoped_user(session, modules='["dashboard", "projects", "timesheets", "reports"]')
    view = client.get(f"{base}/overview", headers=designer).json()
    assert view["bottlenecks"] is None and view["finance"] is None
    assert view["can"]["manage_models"] is False and view["can"]["scenarios"] is False
    listed = client.get(base, params={"prediction_type": "project_final_hours"}, headers=designer).json()
    assert str(hidden.id) not in {r["project_id"] for r in listed["predictions"]}
    assert client.get(base, params={"prediction_type": "finance_collections"}, headers=designer).status_code == 403
    assert client.get(base, params={"prediction_type": "resource_demand"}, headers=designer).status_code == 403
    assert client.get(f"{base}/projects/{hidden.id}", headers=designer).status_code == 404
    assert client.put(f"{base}/settings/project_delivery", json={"enabled": False, "reason": "x"},
                      headers=designer).status_code == 403
    assert client.post(f"{base}/models/project_final_hours/hours-1/activate", json={}, headers=designer).status_code == 403
    assert client.post(f"{base}/run", headers=designer).status_code == 403
    assert client.post(f"{base}/projects/{mine.id}/scenarios", json={"name": "x", "assumptions": {"extra_delay_days": 5}},
                       headers=designer).status_code == 403
    assert client.delete(f"{base}/scenarios/{sid}", headers=designer).status_code == 403
    assert client.delete(f"{base}/scenarios/{sid}", headers=admin).status_code == 204


def test_prediction_job_runs_from_the_queue(session):
    from app.services import job_queue

    job_queue.enqueue_job(session, job_type=job_queue.JOB_PREDICTION_RUN, max_attempts=1)
    assert job_queue.process_due(session, limit=5) == 1
    run = session.scalar(select(PredictionRun).order_by(PredictionRun.started_at.desc()))
    assert run.trigger == "job" and run.status == "succeeded"


def test_phase112_migration_is_idempotent(test_engine):
    from sqlalchemy import inspect

    from app.db.phase112_predictive_schema_sync import ensure_phase112_predictive_foundation

    ensure_phase112_predictive_foundation(test_engine)
    ensure_phase112_predictive_foundation(test_engine)
    columns = {c["name"] for c in inspect(test_engine).get_columns("project_risk_findings")}
    assert {"source", "prediction_id", "triage_status", "recommendation_id"} <= columns
    assert inspect(test_engine).has_table("predictions")
