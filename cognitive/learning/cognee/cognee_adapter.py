"""Cognee Graph-Native Memory Adapter (Task 7.1)

Integrates Cognee's graph-native memory engine:
"Remember, recall, improve, forget" operations over conversational context,
building semantic knowledge graphs of entities, concepts, and relationships.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class CogneeNode:
    """Entity or concept node within the Cognee semantic memory graph."""
    id: str
    name: str
    node_type: str  # e.g., 'concept', 'entity', 'user_preference', 'technology'
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class CogneeEdge:
    """Semantic relationship connecting two nodes."""
    source_id: str
    target_id: str
    relation: str  # e.g., 'USES', 'PREFERS', 'DEPENDS_ON', 'CREATED'
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CogneeKnowledgeGraph:
    """Graph structure produced by cognifying conversational memory."""
    nodes: Dict[str, CogneeNode] = field(default_factory=dict)
    edges: List[CogneeEdge] = field(default_factory=list)

    def add_node(self, node: CogneeNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: CogneeEdge) -> None:
        self.edges.append(edge)

    def get_neighbors(self, node_id: str) -> List[Tuple[CogneeEdge, CogneeNode]]:
        results = []
        for edge in self.edges:
            if edge.source_id == node_id and edge.target_id in self.nodes:
                results.append((edge, self.nodes[edge.target_id]))
            elif edge.target_id == node_id and edge.source_id in self.nodes:
                results.append((edge, self.nodes[edge.source_id]))
        return results


class CogneeAdapter:
    """Adapter for graph-native memory operations: remember, recall, improve, forget."""

    def __init__(self, use_live_cognee: bool = False) -> None:
        self.use_live_cognee = use_live_cognee
        self.graph = CogneeKnowledgeGraph()
        self.memory_store: List[Dict[str, Any]] = []

    def remember(
        self,
        content: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Ingest conversational text or facts into episodic memory."""
        memory_id = f"mem_{len(self.memory_store) + 1}_{abs(hash(content)) % 100000}"
        record = {
            "id": memory_id,
            "content": content,
            "user_id": user_id,
            "session_id": session_id,
            "metadata": metadata or {},
        }
        self.memory_store.append(record)

        # Build / update knowledge graph from ingested conversation
        self._cognify_text(content, user_id)
        return memory_id

    def _cognify_text(self, text: str, user_id: str) -> None:
        """Parse text for entities and semantic relationships, populating knowledge graph."""
        # Ensure user node exists
        user_node_id = f"user_{user_id}"
        if user_node_id not in self.graph.nodes:
            self.graph.add_node(
                CogneeNode(id=user_node_id, name=user_id, node_type="user")
            )

        # Detect tech entities & preferences (heuristic entity extraction)
        patterns = [
            (r'\b(Python|TypeScript|Go|Rust|JavaScript)\b', 'language'),
            (r'\b(LiveKit|TipTap|Mermaid|Tldraw|CopilotKit|Cognee|LangMem|Agenta)\b', 'framework'),
            (r'\b(Layer\s+\d+|L\d+)\b', 'architecture_layer'),
            (r'\b(PostgreSQL|Redis|Neo4j|SQLite|VectorDB)\b', 'database'),
        ]

        found_nodes: List[CogneeNode] = []
        for pattern, ntype in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1).title()
                node_id = f"{ntype}_{val.lower().replace(' ', '_')}"
                if node_id not in self.graph.nodes:
                    node = CogneeNode(id=node_id, name=val, node_type=ntype)
                    self.graph.add_node(node)
                else:
                    node = self.graph.nodes[node_id]
                found_nodes.append(node)

                # Link user to referenced technologies/concepts
                self.graph.add_edge(
                    CogneeEdge(
                        source_id=user_node_id,
                        target_id=node.id,
                        relation="REFERENCED",
                    )
                )

        # Link co-occurring entities
        for i in range(len(found_nodes)):
            for j in range(i + 1, len(found_nodes)):
                n1 = found_nodes[i]
                n2 = found_nodes[j]
                if n1.id != n2.id:
                    self.graph.add_edge(
                        CogneeEdge(
                            source_id=n1.id,
                            target_id=n2.id,
                            relation="CO_OCCURS_WITH",
                        )
                    )

    def recall(self, query: str, top_k: int = 5) -> List[CogneeNode]:
        """Query knowledge graph for relevant concepts and connected neighbors."""
        query_words = set(query.lower().split())
        matched_nodes: List[Tuple[float, CogneeNode]] = []

        for node in self.graph.nodes.values():
            node_words = set(node.name.lower().split()) | set(node.node_type.lower().split())
            intersection = query_words & node_words
            score = len(intersection) / max(1, len(query_words))
            if score > 0 or any(w in node.name.lower() for w in query_words):
                matched_nodes.append((score, node))

        matched_nodes.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in matched_nodes[:top_k]]

    def improve(self, node_id: str, new_attributes: Dict[str, Any]) -> bool:
        """Improve or refine node attributes based on explicit feedback."""
        if node_id in self.graph.nodes:
            self.graph.nodes[node_id].attributes.update(new_attributes)
            return True
        return False

    def forget(self, node_id: str) -> bool:
        """Forget an entity and remove its connected edges from the knowledge graph."""
        if node_id not in self.graph.nodes:
            return False
        del self.graph.nodes[node_id]
        self.graph.edges = [
            e for e in self.graph.edges if e.source_id != node_id and e.target_id != node_id
        ]
        return True

    def get_graph(self) -> CogneeKnowledgeGraph:
        """Return the current semantic knowledge graph."""
        return self.graph

