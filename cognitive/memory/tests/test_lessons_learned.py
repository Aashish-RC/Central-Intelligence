"""Unit tests for Lessons-Learned Auto-Extractor (Features 2.49, 7.27)."""

import pytest
from cognitive.memory.core.models import Turn, TurnRole
from cognitive.memory.engine import MemoryEngine
from cognitive.memory.lessons import (
    LessonCategory,
    LessonRecord,
    LessonStore,
    LessonsLearnedExtractor,
)


@pytest.fixture
def extractor():
    return LessonsLearnedExtractor()


@pytest.fixture
def store():
    return LessonStore(db_path=":memory:")


def test_user_correction_extraction(extractor):
    turn = Turn(
        session_id="s1",
        user_id="user1",
        role=TurnRole.USER,
        content="No, that's wrong; never call the raw API directly. Always remember to use the unified client.",
    )
    lessons = extractor.extract_from_turns([turn])
    assert len(lessons) >= 1
    lesson = lessons[0]
    assert lesson.confidence >= 0.9
    assert "use the unified client" in lesson.rule.lower() or "unified client" in lesson.resolution.lower()


def test_tool_error_recovery_extraction(extractor):
    turn_err = Turn(
        session_id="s2",
        user_id="bot",
        role=TurnRole.TOOL,
        content="Error: ModuleNotFoundError: No module named 'temporalio'",
    )
    turn_fix = Turn(
        session_id="s2",
        user_id="bot",
        role=TurnRole.ASSISTANT,
        content="Installed package via pip install temporalio and imported successfully.",
    )
    lessons = extractor.extract_from_turns([turn_err, turn_fix])
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.category == LessonCategory.ENVIRONMENT_CONFIG
    assert "temporalio" in lesson.trigger_context.lower() or "temporalio" in lesson.rule.lower()


def test_structured_reflection_extraction(extractor):
    turn = Turn(
        session_id="s3",
        user_id="assistant",
        role=TurnRole.ASSISTANT,
        content="Post-mortem analysis complete. Lesson learned: always verify schema migrations before running SQLite queries.",
    )
    lessons = extractor.extract_from_turns([turn])
    assert len(lessons) == 1
    assert "schema migrations" in lessons[0].rule.lower()


def test_lesson_store_persistence_and_relevance_ranking(store):
    l1 = LessonRecord(
        lesson_id="lsn_1",
        title="Docker Port Conflict",
        category=LessonCategory.TOOL_FAILURE,
        trigger_context="docker compose container port conflict",
        mistake="Port 6379 already allocated",
        resolution="Kill existing redis process or remap port to 6380",
        rule="When docker port is busy, check running containers and remap host port",
        confidence=0.9,
    )
    l2 = LessonRecord(
        lesson_id="lsn_2",
        title="Temporal Heartbeat Timeout",
        category=LessonCategory.API_MISMATCH,
        trigger_context="temporal workflow worker heartbeat timeout",
        mistake="Heartbeat interval exceeded 30s",
        resolution="Set worker heartbeat throttle to 5s",
        rule="Configure activity heartbeat interval to 1/3 of timeout",
        confidence=0.95,
    )

    store.save_lesson(l1)
    store.save_lesson(l2)

    # Query for docker issues
    docker_hits = store.query_lessons("docker container conflict")
    assert len(docker_hits) >= 1
    assert docker_hits[0].lesson_id == "lsn_1"

    # Query for temporal issues
    temporal_hits = store.query_lessons("temporal worker timeout")
    assert len(temporal_hits) >= 1
    assert temporal_hits[0].lesson_id == "lsn_2"

    # Verify application count increment
    store.record_application("lsn_1")
    updated = store.get_lesson("lsn_1")
    assert updated is not None
    assert updated.application_count == 1


def test_memory_engine_lesson_integration():
    engine = MemoryEngine()

    turns = [
        Turn(
            session_id="s_eng",
            user_id="alice",
            role=TurnRole.USER,
            content="Stop using print statements, use structured logger instead.",
        )
    ]

    extracted = engine.extract_and_store_lessons(turns)
    assert len(extracted) >= 1

    hits = engine.get_relevant_lessons("logger print statements")
    assert len(hits) >= 1
    assert "structured logger" in hits[0].rule.lower() or "logger" in hits[0].resolution.lower()
