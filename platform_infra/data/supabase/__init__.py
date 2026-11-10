"""Supabase PostgreSQL adapter with RLS, pgvector, and Apache AGE (Task 15.1)."""

from platform_infra.data.supabase.supabase_adapter import (
    SupabaseAdapter,
    VectorRecord,
    GraphNode,
    GraphEdge,
)

__all__ = ["SupabaseAdapter", "VectorRecord", "GraphNode", "GraphEdge"]

