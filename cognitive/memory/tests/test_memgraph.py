"""Unit and integration tests for Tier 4: Memgraph Knowledge Graph Store."""

import pytest
from memory.tiers.graph.memgraph_adapter import MemgraphAdapter
from memory.engine import MemoryEngine
from memory.config import MemoryConfig


@pytest.fixture
def graph_adapter():
    """Return an in-memory graph adapter for hermetic execution."""
    return MemgraphAdapter(host=":memory:")


def test_memgraph_health(graph_adapter):
    """Test health check returns True."""
    assert graph_adapter.check_health() is True
    assert graph_adapter.is_in_memory is True


def test_add_entity(graph_adapter):
    """Test adding entity nodes with properties."""
    user_id = "test_user_01"
    name = graph_adapter.add_entity(
        user_id=user_id,
        name="Alice",
        entity_type="Person",
        properties={"title": "Software Engineer", "team": "Core AI"},
    )
    assert name == "Alice"


def test_cypher_who_manages_alice(graph_adapter):
    """Test querying 'who manages Alice?' via Cypher."""
    user_id = "test_user_01"
    # Bob manages Alice
    graph_adapter.add_relationship(
        user_id=user_id,
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )

    # Cypher query: MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name
    results = graph_adapter.execute_query(
        "MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name"
    )

    assert len(results) > 0
    assert results[0]["m.name"] == "Bob"


def test_multi_hop_query(graph_adapter):
    """Test multi-hop relationship traversal (Carol manages Bob, Bob manages Alice)."""
    user_id = "test_user_01"
    graph_adapter.add_relationship(
        user_id=user_id,
        source="Carol",
        relation="MANAGES",
        target="Bob",
    )
    graph_adapter.add_relationship(
        user_id=user_id,
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )

    # 2-hop traversal from Carol down management chain
    hops = graph_adapter.multi_hop_query(
        user_id=user_id,
        start_entity="Carol",
        relation="MANAGES",
        hops=2,
    )

    targets = [h["target"] for h in hops]
    assert "Bob" in targets
    assert "Alice" in targets

    # Verify depth tracking
    alice_hop = next(h for h in hops if h["target"] == "Alice")
    assert alice_hop["depth"] == 2
    assert alice_hop["path"] == ["Carol", "MANAGES", "Bob", "MANAGES", "Alice"]


def test_conflict_resolution_against_graph(graph_adapter):
    """Test conflict resolution when relationship changes (Alice moves from Bob to Dave)."""
    user_id = "test_user_01"
    # Initial state: Bob manages Alice
    graph_adapter.add_relationship(
        user_id=user_id,
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )
    initial_results = graph_adapter.execute_query(
        "MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name"
    )
    assert len(initial_results) == 1
    assert initial_results[0]["m.name"] == "Bob"

    # Conflict resolution: remove old relationship and add Dave manages Alice
    removed = graph_adapter.delete_relationship(
        user_id=user_id,
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )
    assert removed is True

    graph_adapter.add_relationship(
        user_id=user_id,
        source="Dave",
        relation="MANAGES",
        target="Alice",
    )

    updated_results = graph_adapter.execute_query(
        "MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name"
    )
    assert len(updated_results) == 1
    assert updated_results[0]["m.name"] == "Dave"


def test_memory_engine_graph_tier_integration():
    """Test full integration of Tier 4 Graph in MemoryEngine."""
    config = MemoryConfig(memgraph_host=":memory:")
    engine = MemoryEngine(config=config)

    # Verify Tier 4 is instantiated
    assert hasattr(engine, "graph")
    assert engine.graph is not None

    user_id = "user_corp_01"
    # Add relationship via engine API
    engine.add_relationship(
        user_id=user_id,
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )

    # Query Cypher through engine
    res = engine.query_graph("MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name")
    assert len(res) == 1
    assert res[0]["m.name"] == "Bob"

    # Multi-hop through engine
    engine.add_relationship(
        user_id=user_id,
        source="Carol",
        relation="MANAGES",
        target="Bob",
    )
    chain = engine.multi_hop_query(
        user_id=user_id,
        start_entity="Carol",
        relation="MANAGES",
        hops=2,
    )
    assert len(chain) == 2
    assert [c["target"] for c in chain] == ["Bob", "Alice"]


def test_default_memory_engine_uses_apache_age():
    """Default MemoryConfig routes Tier 4 graph queries through ApacheAGEAdapter."""
    from memory.tiers.graph.age_adapter import ApacheAGEAdapter
    from memory.config import GraphStoreBackend

    config = MemoryConfig(memgraph_host=":memory:")
    assert config.graph_backend == GraphStoreBackend.POSTGRES_AGE
    engine = MemoryEngine(config=config)
    assert isinstance(engine.graph, ApacheAGEAdapter)
    assert engine.graph.check_health() is True

    engine.add_relationship(
        user_id="age_user",
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )
    res = engine.query_graph("MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name")
    assert len(res) == 1
    assert res[0]["m.name"] == "Bob"

    assert engine.graph.delete_relationship(
        user_id="age_user",
        source="Bob",
        relation="MANAGES",
        target="Alice",
    )
    assert engine.query_graph("MATCH (m)-[:MANAGES]->(a {name: 'Alice'}) RETURN m.name") == []


def test_apache_age_dollar_quote_and_injection_roundtrip():
    """Values containing $$$, $$$$, and SQL/dollar injection must parameterize & round-trip unchanged."""
    import json
    from unittest.mock import MagicMock
    from memory.tiers.graph.age_adapter import ApacheAGEAdapter, _make_dollar_tag

    adversarial_values = [
        "$$$",
        "$$$$",
        "'$$; DROP TABLE x; --",
    ]

    # 1. Hermetic round-trip on entities, relationships, properties, and parameterized queries
    adapter = ApacheAGEAdapter(postgres_url=":memory:")
    for val in adversarial_values:
        adapter.add_entity(
            user_id="sec_user",
            name=val,
            entity_type="Entity",
            properties={"raw": val},
        )
        rows = adapter.execute_query(
            "MATCH (n {name: $name, user_id: $user_id}) RETURN n.name AS name, n.props_json AS props_json",
            params={"name": val, "user_id": "sec_user"},
        )
        assert len(rows) == 1
        assert rows[0]["name"] == val
        assert json.loads(rows[0]["props_json"])["raw"] == val

        adapter.add_relationship(
            user_id="sec_user",
            source="RootNode",
            relation="TAGGED",
            target=val,
            properties={"marker": val},
        )

    hops = adapter.multi_hop_query(user_id="sec_user", start_entity="RootNode", relation="TAGGED", hops=1)
    assert {h["target"] for h in hops} == set(adversarial_values)
    for hop in hops:
        assert hop["properties"]["marker"] in adversarial_values

    # 2. Verify live SQL layer uses random dollar-quote tags & out-of-band bound parameters
    executed: list[tuple[str, object]] = []
    mock_cursor = MagicMock()
    mock_cursor.description = [("c0",)]
    mock_cursor.fetchall.return_value = [('"' + adversarial_values[2] + '"',)]

    def record_execute(sql, args=None):
        executed.append((sql, args))

    mock_cursor.execute.side_effect = record_execute
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    live_like = ApacheAGEAdapter(postgres_url=":memory:")
    live_like._is_in_memory = False
    live_like._conn = mock_conn

    for val in adversarial_values:
        executed.clear()
        live_like.add_entity(
            user_id="sec_user",
            name=val,
            properties={"payload": val},
        )
        cypher_calls = [(sql, args) for sql, args in executed if "ag_catalog.cypher(" in sql]
        assert cypher_calls
        for sql, args in cypher_calls:
            assert val not in sql
            assert "$$$" not in sql
            assert "DROP TABLE" not in sql
            assert "%s" in sql
            assert args is not None and len(args) == 1
            bound = json.loads(args[0])
            assert bound["name"] == val
            assert json.loads(bound["props_json"])["payload"] == val

    # 3. Verify explicit dollar-tag collision guard
    with pytest.raises(ValueError):
        _make_dollar_tag("MATCH (n {name: '$age_deadbeef$'}) RETURN n", tag_prefix="$age_deadbeef$")

