"""Unit tests for MeilisearchClient, real-time ingestion, and sub-500ms query capability."""

import time
from unittest.mock import MagicMock, patch
import pytest

import search
from search import MeilisearchClient, query, ingest_conversation_turn, subscribe_to_memory_writes
from search.core.models import CorpusType, SearchQuery


def test_conversation_turn_queryable_within_500ms():
    """Done When criteria: Adding a conversation turn makes it queryable via search.query('needle') within 500ms."""
    session_id = "sess_meili_test_1"
    message_id = "msg_001"
    unique_needle = f"quantum_needle_{int(time.time() * 1000)}"

    # 1. Ingest conversation turn
    start_ingest = time.perf_counter()
    doc = ingest_conversation_turn(
        session_id=session_id,
        message_id=message_id,
        role="user",
        text=f"Please remember this important secret key: {unique_needle} for our project.",
    )
    assert doc.id == f"conv:{session_id}:{message_id}"
    assert doc.corpus_type == CorpusType.CONVERSATION

    # 2. Query for the needle and verify latency < 500ms
    start_query = time.perf_counter()
    results = search.query(unique_needle)
    elapsed_ms = (time.perf_counter() - start_query) * 1000.0

    assert elapsed_ms < 500.0, f"Query took {elapsed_ms:.2f}ms, exceeding 500ms SLA"
    assert len(results) >= 1
    assert any(unique_needle in r.document.content for r in results)


def test_subscribe_to_memory_writes_realtime():
    """Verify subscription to memory engine automatically indexes turns."""
    mock_memory_engine = MagicMock()
    mock_memory_engine.remember.return_value = MagicMock(id="mem_fact_123")

    unsubscribe = subscribe_to_memory_writes(mock_memory_engine)

    unique_fact = f"fact_needle_{int(time.time() * 1000)}"
    mock_memory_engine.remember("user_100", f"User favorite language is {unique_fact}")

    # Query search
    res = search.query(unique_fact)
    assert len(res) >= 1
    assert any(unique_fact in r.document.content for r in res)

    unsubscribe()


def test_meilisearch_mock_http_api_search():
    client = MeilisearchClient(url="http://localhost:7700", master_key="test_key")
    client._server_available = True

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"hits": [{"id": "conv_1", "raw_id": "conv:1", "corpus_type": "conversation", "title": "Chat", "content": "mock meili search result"}]}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = client.query("meili search")
        assert len(res) >= 1
        assert "mock meili search result" in res[0].document.content
