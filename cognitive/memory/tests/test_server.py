"""Tests for FastAPI REST endpoints in server/app.py."""

import pytest
from fastapi.testclient import TestClient
from memory.server.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "working_tier" in data
    assert "facts_tier" in data
    assert "semantic_tier" in data


def test_remember_and_recall_rest_flow(client):
    user_id = "rest_alice"
    session_id = "session_rest_1"

    # POST /api/v1/remember
    rem_res = client.post(
        "/api/v1/remember",
        json={
            "user_id": user_id,
            "text": "My name is Alice and I only write Go code now, dropped Rust.",
            "session_id": session_id,
        },
    )
    assert rem_res.status_code == 200
    rem_data = rem_res.json()
    assert rem_data["user_id"] == user_id
    assert len(rem_data["facts_saved"]) > 0

    # GET /api/v1/facts/{user_id}
    facts_res = client.get(f"/api/v1/facts/{user_id}")
    assert facts_res.status_code == 200
    facts_data = facts_res.json()
    assert facts_data["user_id"] == user_id
    assert len(facts_data["active_facts"]) > 0

    # POST /api/v1/recall
    rec_res = client.post(
        "/api/v1/recall",
        json={
            "user_id": user_id,
            "query": "What language should we use?",
            "session_id": session_id,
        },
    )
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert "formatted_prompt" in rec_data
    assert rec_data["token_count"] <= 500
    assert "preferred_language: Go" in rec_data["formatted_prompt"]

    # POST /api/v1/consolidate
    cons_res = client.post(
        "/api/v1/consolidate",
        json={"user_id": user_id, "session_id": session_id},
    )
    assert cons_res.status_code == 200
    cons_data = cons_res.json()
    assert cons_data["session_id"] == session_id
    assert cons_data["purged_from_working"] is True
