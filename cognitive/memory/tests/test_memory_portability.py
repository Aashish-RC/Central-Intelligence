"""Unit and integration tests for Cross-Assistant Memory Portability (Features 2.46, 2.50)."""

import json
import tempfile
import pytest
from cognitive.memory.config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)
from cognitive.memory.engine import MemoryEngine
from cognitive.memory.portability import (
    MemoryPortabilityManager,
    MemoryPortabilityFormat,
    ChatGPTTranslator,
    ClaudeTranslator,
    StandardCITranslator,
    StandardTurnRecord,
    StandardFactRecord,
)


@pytest.fixture
def memory_fixture():
    wal_dir = tempfile.mkdtemp()
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=wal_dir,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=db_path,
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        collection_name="test_portability_coll",
    )
    engine = MemoryEngine(config=config)
    yield engine


def test_chatgpt_translator_parse_and_format():
    translator = ChatGPTTranslator()
    chatgpt_export = {
        "title": "Architecture Discussion",
        "create_time": 1700000000,
        "mapping": {
            "node_1": {
                "id": "node_1",
                "message": {
                    "id": "msg_1",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["I prefer Postgres over MongoDB for relational workloads"]},
                    "create_time": 1700000001,
                },
            },
            "node_2": {
                "id": "node_2",
                "message": {
                    "id": "msg_2",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["Postgres provides strong ACID guarantees and rich indexing."]},
                    "create_time": 1700000002,
                },
            },
        },
    }

    turns, facts = translator.parse(chatgpt_export, user_id="user_test")
    assert len(turns) == 2
    assert turns[0].role == "user"
    assert "Postgres" in turns[0].content
    assert turns[1].role == "assistant"
    assert "ACID" in turns[1].content

    # Test reverse format to ChatGPT structure
    formatted = translator.format(turns, facts, user_id="user_test")
    assert formatted["format"] == "chatgpt_export"
    assert "mapping" in formatted
    assert len(formatted["mapping"]) == 2


def test_claude_translator_parse_and_format():
    translator = ClaudeTranslator()
    claude_export = {
        "uuid": "claude-conv-123",
        "name": "Design Sync",
        "chat_messages": [
            {
                "uuid": "claude-msg-1",
                "sender": "human",
                "text": "My primary cloud provider is GCP.",
                "created_at": "2026-05-01T12:00:00Z",
            },
            {
                "uuid": "claude-msg-2",
                "sender": "assistant",
                "text": "Noted. We will configure BigQuery and GCS adapters.",
                "created_at": "2026-05-01T12:00:05Z",
            },
        ],
    }

    turns, facts = translator.parse(claude_export, user_id="user_test")
    assert len(turns) == 2
    assert turns[0].role == "user"
    assert "GCP" in turns[0].content
    assert turns[1].role == "assistant"
    assert "BigQuery" in turns[1].content

    # Reverse formatting to Claude JSON
    formatted = translator.format(turns, facts, user_id="user_test")
    assert formatted["format"] == "claude_export"
    assert len(formatted["chat_messages"]) == 2
    assert formatted["chat_messages"][0]["sender"] == "human"


def test_ci_standard_translator_roundtrip():
    translator = StandardCITranslator()
    sample_turns = [
        StandardTurnRecord(id="t1", role="user", content="Deploying service to production.", session_id="s1"),
        StandardTurnRecord(id="t2", role="assistant", content="Deployment pipeline initialized.", session_id="s1"),
    ]
    sample_facts = [
        StandardFactRecord(subject="User", predicate="operates", object="Kubernetes", confidence_score=0.95),
    ]

    export_dict = translator.format(sample_turns, sample_facts, user_id="user_test")
    assert export_dict["user_id"] == "user_test"
    assert len(export_dict["turns"]) == 2
    assert len(export_dict["facts"]) == 1

    parsed_turns, parsed_facts = translator.parse(export_dict, user_id="user_test")
    assert len(parsed_turns) == 2
    assert parsed_facts[0].subject == "User"
    assert parsed_facts[0].object == "Kubernetes"


def test_memory_engine_import_and_export(memory_fixture):
    engine = memory_fixture
    user_id = "user_cross_assistant"

    claude_payload = {
        "uuid": "claude-session-99",
        "chat_messages": [
            {
                "uuid": "m1",
                "sender": "human",
                "text": "I am allergic to peanuts.",
            },
        ],
    }

    # Import into MemoryEngine
    stats = engine.import_memory(
        raw_data=claude_payload,
        source_format=MemoryPortabilityFormat.CLAUDE,
        user_id=user_id,
    )

    assert stats.success is True
    assert stats.turns_imported == 1
    assert stats.sessions_discovered == 1

    # Verify working memory contains the turn
    active_turns = engine.working.get_active_window(session_id="claude-session-99")
    assert len(active_turns) >= 1
    assert "allergic to peanuts" in active_turns[0].content

    # Export to ChatGPT format
    chatgpt_export = engine.export_memory(
        user_id=user_id,
        target_format=MemoryPortabilityFormat.CHATGPT,
        session_id="claude-session-99",
    )
    assert chatgpt_export["format"] == "chatgpt_export"
    assert len(chatgpt_export["mapping"]) >= 1
