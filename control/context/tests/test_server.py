"""Test suite for Layer 9 Context Engineering FastAPI Server."""

import pytest
from fastapi.testclient import TestClient
from control.context.server import app

client = TestClient(app)


def test_server_assemble_context_endpoint():
    payload = {
        "system_instructions": "Enterprise Gateway context.",
        "memory_records": [{"key": "env", "value": "production"}],
        "retrieved_knowledge": [{"doc_id": "doc1", "content": "Security spec guidelines."}],
        "active_tools": [{"name": "calculator", "description": "Arithmetic tool"}],
        "conversation_history": [{"role": "user", "content": "Compute 42 * 2"}],
        "user_id": "test_user",
    }
    response = client.post("/v1/context/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_tokens"] > 0
    assert "Enterprise Gateway context." in data["full_prompt"]
    assert "calculator" in data["full_prompt"]
    assert "Security spec guidelines." in data["full_prompt"]
    assert "memory" in data["sources_included"]
    assert "knowledge" in data["sources_included"]
    assert "tools" in data["sources_included"]
