"""Unit tests for Supabase Adapter (Task 15.1)."""

import pytest
from platform.data.supabase.supabase_adapter import SupabaseAdapter


def test_can_store_relational_data_with_rls():
    supabase = SupabaseAdapter()
    supabase.enable_rls("user_profiles")

    # Insert rows for two separate users
    supabase.insert_row(
        table_name="user_profiles",
        data={"name": "Alice Developer", "tier": "enterprise"},
        user_id="user_alice",
    )
    supabase.insert_row(
        table_name="user_profiles",
        data={"name": "Bob Analyst", "tier": "free"},
        user_id="user_bob",
    )

    # Alice queries with RLS enabled: should only see Alice's row
    alice_rows = supabase.query_table("user_profiles", current_user_id="user_alice")
    assert len(alice_rows) == 1
    assert alice_rows[0]["name"] == "Alice Developer"

    # Bob queries with RLS enabled: should only see Bob's row
    bob_rows = supabase.query_table("user_profiles", current_user_id="user_bob")
    assert len(bob_rows) == 1
    assert bob_rows[0]["name"] == "Bob Analyst"

    # Service role bypasses RLS
    all_rows = supabase.query_table("user_profiles", current_user_id="anonymous", is_service_role=True)
    assert len(all_rows) == 2


def test_pgvector_semantic_search():
    supabase = SupabaseAdapter()

    # Store embeddings in pgvector
    supabase.store_embedding(
        collection="knowledge_vectors",
        record_id="vec_1",
        vector=[1.0, 0.0, 0.0],
        document="Introduction to quantum computing and qubits.",
        user_id="alice",
    )
    supabase.store_embedding(
        collection="knowledge_vectors",
        record_id="vec_2",
        vector=[0.0, 1.0, 0.0],
        document="Culinary recipes for Italian pasta sauces.",
        user_id="alice",
    )

    # Search with query vector closest to quantum computing
    results = supabase.search_embeddings(
        collection="knowledge_vectors",
        query_vector=[0.95, 0.05, 0.0],
        top_k=1,
    )

    assert len(results) == 1
    top_doc = results[0]
    assert "quantum computing" in top_doc["document"]
    assert top_doc["similarity"] > 0.9


def test_apache_age_graph_queries():
    supabase = SupabaseAdapter()
    graph_name = "knowledge_graph"

    # Add vertices and edge
    supabase.add_graph_node(
        graph_name=graph_name,
        node_id="person_alice",
        label="Person",
        properties={"name": "Alice", "role": "Architect"},
    )
    supabase.add_graph_node(
        graph_name=graph_name,
        node_id="proj_central",
        label="Project",
        properties={"name": "Central Intelligence"},
    )
    supabase.add_graph_edge(
        graph_name=graph_name,
        edge_id="edge_1",
        label="LEADS",
        from_node="person_alice",
        to_node="proj_central",
    )

    # Execute Cypher query
    cypher = "MATCH (p:Person)-[r:LEADS]->(proj:Project)"
    results = supabase.execute_cypher(graph_name, cypher)

    assert len(results) == 1
    record = results[0]
    assert record["p"]["name"] == "Alice"
    assert record["r"] == "LEADS"
    assert record["proj"]["name"] == "Central Intelligence"
