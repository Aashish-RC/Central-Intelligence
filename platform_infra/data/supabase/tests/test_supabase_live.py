"""Live integration tests for Supabase PostgreSQL + pgvector + Apache AGE adapter (Layer 15).

Executed against a live PostgreSQL (5432) and Apache AGE (5433) instance.
Skipped in hermetic/CI test mode unless POSTGRES_LIVE_URL is explicitly set.
"""

from __future__ import annotations

import os
import uuid
import pytest

from platform_infra.data.supabase.supabase_adapter import SupabaseAdapter
from control.safety.production_guard import ProductionSafetyError

pytestmark = pytest.mark.live

POSTGRES_LIVE_URL = os.getenv("POSTGRES_LIVE_URL")


def test_relational_row_persists_across_restart():
    """Verify relational rows written to Postgres persist across distinct adapter instances."""
    if not POSTGRES_LIVE_URL:
        pytest.skip("POSTGRES_LIVE_URL not set; skipping live Supabase tests")

    table_name = f"e2e_table_{uuid.uuid4().hex[:8]}"
    adapter1 = SupabaseAdapter(connection_url=POSTGRES_LIVE_URL, _defer_prod_check=True)
    adapter1.adapter_mode = "live"

    inserted = adapter1.insert_row(
        table_name=table_name,
        data={"title": "Persistent Doc", "version": "1"},
        user_id="user_alice",
    )
    assert inserted["title"] == "Persistent Doc"

    # Brand new adapter instance simulating process restart
    adapter2 = SupabaseAdapter(connection_url=POSTGRES_LIVE_URL, _defer_prod_check=True)
    adapter2.adapter_mode = "live"

    rows = adapter2.query_table(table_name=table_name, current_user_id="user_alice")
    assert len(rows) == 1
    assert rows[0]["title"] == "Persistent Doc"
    assert rows[0]["user_id"] == "user_alice"


def test_rls_blocks_cross_user_access():
    """Verify SQL-level RLS filtering restricts queries to authorized user."""
    if not POSTGRES_LIVE_URL:
        pytest.skip("POSTGRES_LIVE_URL not set; skipping live Supabase tests")

    table_name = f"e2e_rls_{uuid.uuid4().hex[:8]}"
    adapter = SupabaseAdapter(connection_url=POSTGRES_LIVE_URL, _defer_prod_check=True)
    adapter.adapter_mode = "live"
    adapter.enable_rls(table_name)

    adapter.insert_row(
        table_name=table_name,
        data={"content": "Alice Secret"},
        user_id="alice",
    )

    # Bob should receive empty list
    bob_rows = adapter.query_table(table_name, current_user_id="bob", is_service_role=False)
    assert len(bob_rows) == 0

    # Alice should receive 1 row
    alice_rows = adapter.query_table(table_name, current_user_id="alice", is_service_role=False)
    assert len(alice_rows) == 1
    assert alice_rows[0]["content"] == "Alice Secret"

    # Service role bypasses RLS
    admin_rows = adapter.query_table(table_name, current_user_id="bob", is_service_role=True)
    assert len(admin_rows) == 1


def test_embedding_search_returns_correct_order():
    """Verify pgvector cosine similarity search returns nearest embeddings first."""
    if not POSTGRES_LIVE_URL:
        pytest.skip("POSTGRES_LIVE_URL not set; skipping live Supabase tests")

    collection = f"e2e_vec_{uuid.uuid4().hex[:8]}"
    adapter = SupabaseAdapter(connection_url=POSTGRES_LIVE_URL, _defer_prod_check=True)
    adapter.adapter_mode = "live"

    adapter.store_embedding(collection, "vec_1", [1.0, 0.0, 0.0], "Target match", "user_1")
    adapter.store_embedding(collection, "vec_2", [0.7, 0.7, 0.0], "Partial match", "user_1")
    adapter.store_embedding(collection, "vec_3", [0.0, 1.0, 0.0], "Orthogonal", "user_1")

    results = adapter.search_embeddings(collection, [0.99, 0.01, 0.0], top_k=2, user_id="user_1")
    assert len(results) == 2
    assert results[0]["id"] == "vec_1"
    assert results[0]["similarity"] > results[1]["similarity"]


def test_cypher_query_returns_real_edges():
    """Verify Apache AGE executes Cypher graph queries and returns created edges."""
    if not POSTGRES_LIVE_URL:
        pytest.skip("POSTGRES_LIVE_URL not set; skipping live Supabase tests")

    graph_name = f"e2e_graph_{uuid.uuid4().hex[:8]}"
    adapter = SupabaseAdapter(connection_url=POSTGRES_LIVE_URL, _defer_prod_check=True)
    adapter.adapter_mode = "live"

    adapter.create_graph(graph_name)
    adapter.add_graph_node(graph_name, "node_a", "Service", {"name": "Auth"})
    adapter.add_graph_node(graph_name, "node_b", "Database", {"name": "Postgres"})
    adapter.add_graph_edge(graph_name, "edge_ab", "CONNECTS_TO", "node_a", "node_b", {"protocol": "tcp"})

    results = adapter.execute_cypher(graph_name, "MATCH (n)-[r]->(m) RETURN n,r,m")
    assert len(results) >= 1


def test_postgres_down_fails_closed(monkeypatch):
    """When ADAPTER_MODE=live and Postgres is down, fail closed with ProductionSafetyError."""
    monkeypatch.setenv("ADAPTER_MODE", "live")
    monkeypatch.delenv("CI_TEST_MODE", raising=False)

    adapter = SupabaseAdapter(
        connection_url="postgresql://postgres:postgres@127.0.0.1:59999/postgres",
        _defer_prod_check=True,
    )
    adapter.adapter_mode = "live"

    with pytest.raises(ProductionSafetyError):
        adapter.insert_row("test_table", {"data": "test"}, "alice")
