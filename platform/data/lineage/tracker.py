"""Data Lineage Tracker (L15 Data & Messaging - Task 15.36).

Tracks end-to-end data provenance, origins, transformations, and consumption.
Enables full bidirectional provenance queries:
- Upstream lineage (trace any data item back to original source roots)
- Downstream lineage (trace any data item forward to all consumers)
"""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    SOURCE = "source"
    DATA_ITEM = "data_item"
    TRANSFORMATION = "transformation"
    CONSUMER = "consumer"


class RelationType(str, Enum):
    ORIGINATES_FROM = "originates_from"
    DERIVED_FROM = "derived_from"
    TRANSFORMED_BY = "transformed_by"
    CONSUMED_BY = "consumed_by"


@dataclass
class LineageNode:
    """A node in the data lineage DAG."""
    node_id: str
    node_type: NodeType
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class LineageEdge:
    """A directed edge in the data lineage DAG."""
    edge_id: str
    from_node_id: str
    to_node_id: str
    relation: RelationType
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class DataLineageTracker:
    """Manages lineage graph, recording sources, transformations, and consumers."""

    def __init__(self) -> None:
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: Dict[str, LineageEdge] = {}
        # from_node -> list of outgoing edges
        self._out_edges: Dict[str, List[LineageEdge]] = collections.defaultdict(list)
        # to_node -> list of incoming edges
        self._in_edges: Dict[str, List[LineageEdge]] = collections.defaultdict(list)

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Register or update a lineage node."""
        if node_id in self._nodes:
            node = self._nodes[node_id]
            if metadata:
                node.metadata.update(metadata)
            return node

        node = LineageNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            metadata=metadata or {},
        )
        self._nodes[node_id] = node
        return node

    def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        relation: RelationType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageEdge:
        """Create a directed lineage edge from from_node_id to to_node_id."""
        edge_id = f"edge_{from_node_id}_{relation.value}_{to_node_id}"
        if edge_id in self._edges:
            return self._edges[edge_id]

        edge = LineageEdge(
            edge_id=edge_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation=relation,
            metadata=metadata or {},
        )
        self._edges[edge_id] = edge
        self._out_edges[from_node_id].append(edge)
        self._in_edges[to_node_id].append(edge)
        return edge

    def record_source(
        self,
        source_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Record an original data source (e.g., API, CSV, User input, Postgres)."""
        return self.add_node(
            node_id=source_id,
            node_type=NodeType.SOURCE,
            name=name,
            metadata=metadata,
        )

    def record_data_item(
        self,
        item_id: str,
        name: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Record a data item and connect to its source if given."""
        node = self.add_node(
            node_id=item_id,
            node_type=NodeType.DATA_ITEM,
            name=name,
            metadata=metadata,
        )
        if source_id:
            if source_id not in self._nodes:
                self.record_source(source_id, name=source_id)
            self.add_edge(source_id, item_id, RelationType.ORIGINATES_FROM)
        return node

    def record_derivation(
        self,
        derived_item_id: str,
        name: str,
        parent_item_ids: List[str],
        transformation_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Record derived data item from one or more parent items via a transformation."""
        transform_id = f"tx_{transformation_name}_{int(time.time()*1000)}"
        self.add_node(
            node_id=transform_id,
            node_type=NodeType.TRANSFORMATION,
            name=transformation_name,
            metadata=metadata,
        )

        for p_id in parent_item_ids:
            if p_id not in self._nodes:
                self.record_data_item(p_id, name=p_id)
            self.add_edge(p_id, transform_id, RelationType.TRANSFORMED_BY)

        derived = self.add_node(
            node_id=derived_item_id,
            node_type=NodeType.DATA_ITEM,
            name=name,
            metadata=metadata,
        )
        self.add_edge(transform_id, derived_item_id, RelationType.DERIVED_FROM)
        return derived

    def record_consumption(
        self,
        consumer_id: str,
        consumer_name: str,
        item_id: str,
        action: str = "read",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LineageNode:
        """Record an entity or model consuming a data item."""
        consumer = self.add_node(
            node_id=consumer_id,
            node_type=NodeType.CONSUMER,
            name=consumer_name,
            metadata=metadata,
        )
        if item_id not in self._nodes:
            self.record_data_item(item_id, name=item_id)

        meta = {"action": action}
        if metadata:
            meta.update(metadata)

        self.add_edge(item_id, consumer_id, RelationType.CONSUMED_BY, metadata=meta)
        return consumer

    def get_upstream_sources(self, item_id: str) -> List[LineageNode]:
        """Trace backwards to find all root sources that contributed to this item."""
        visited: Set[str] = set()
        queue: collections.deque[str] = collections.deque([item_id])
        sources: List[LineageNode] = []

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            node = self._nodes.get(curr)
            if node and node.node_type == NodeType.SOURCE:
                sources.append(node)

            for in_edge in self._in_edges.get(curr, []):
                if in_edge.from_node_id not in visited:
                    queue.append(in_edge.from_node_id)

        return sources

    def get_downstream_consumers(self, item_id: str) -> List[LineageNode]:
        """Trace forwards to find all consumers that used this data item or its derivatives."""
        visited: Set[str] = set()
        queue: collections.deque[str] = collections.deque([item_id])
        consumers: List[LineageNode] = []

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            node = self._nodes.get(curr)
            if node and node.node_type == NodeType.CONSUMER:
                consumers.append(node)

            for out_edge in self._out_edges.get(curr, []):
                if out_edge.to_node_id not in visited:
                    queue.append(out_edge.to_node_id)

        return consumers

    def trace_full_lineage(self, item_id: str) -> Dict[str, Any]:
        """Return full upstream and downstream lineage graph for item."""
        sources = self.get_upstream_sources(item_id)
        consumers = self.get_downstream_consumers(item_id)
        target_node = self._nodes.get(item_id)

        return {
            "item_id": item_id,
            "target": target_node.__dict__ if target_node else None,
            "sources": [s.__dict__ for s in sources],
            "consumers": [c.__dict__ for c in consumers],
            "total_sources": len(sources),
            "total_consumers": len(consumers),
        }
