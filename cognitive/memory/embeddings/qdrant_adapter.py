"""
Pheonix Qdrant Adapter (Embeddings / Vector Tier)
Exposes QdrantAdapter with startup health checks and vector store operations.
"""

from ..tiers.semantic.qdrant_adapter import QdrantAdapter

__all__ = ["QdrantAdapter"]
