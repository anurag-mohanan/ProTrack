from sqlalchemy import select

from app.models.models import TaskType
from app.services.task_type_matching_service import match_task_type, normalize_task_type_value
from tests.conftest import IDS


def test_normalize_task_type_value_collapses_variants():
    assert normalize_task_type_value(" Sub-Task ") == "sub task"
    assert normalize_task_type_value("sub_task") == "sub task"
    assert normalize_task_type_value("SUB   TASK") == "sub task"


def test_match_task_type_uses_aliases(test_session_factory):
    db = test_session_factory()
    try:
        existing = db.scalar(
            select(TaskType).where(
                TaskType.stream_id == IDS["stream"],
                TaskType.name == "2D Drawings",
            )
        )
        if existing is None:
            db.add(
                TaskType(
                    stream_id=IDS["stream"],
                    name="2D Drawings",
                    description="Seeded by test",
                    is_active=True,
                    is_billable=True,
                )
            )
            db.commit()

        matched = match_task_type(
            db,
            excel_task_name="Drawing",
            stream_id=IDS["stream"],
            auto_create=False,
        )
        assert matched.task_type is not None
        assert matched.task_type.name == "2D Drawings"
    finally:
        db.close()


def test_match_task_type_can_auto_create_missing(test_session_factory):
    db = test_session_factory()
    try:
        before = db.scalar(
            select(TaskType).where(
                TaskType.stream_id == IDS["stream"],
                TaskType.name == "Sub Task",
            )
        )
        assert before is None

        matched = match_task_type(
            db,
            excel_task_name="Sub-Task",
            stream_id=IDS["stream"],
            auto_create=True,
        )
        assert matched.task_type is not None
        assert matched.created is True
        assert matched.task_type.name == "Sub Task"
    finally:
        db.close()

