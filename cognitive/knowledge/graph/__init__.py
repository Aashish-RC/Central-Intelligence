"""GraphRAG module for Layer 3 Knowledge (Postgres + Apache AGE default, FalkorDB opt-in)."""

from .age_adapter import ApacheAGEGraphAdapter
from .falkordb_adapter import FalkorDBAdapter

__all__ = ["ApacheAGEGraphAdapter", "FalkorDBAdapter"]

