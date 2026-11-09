"""Abstract Base Classes defining the contracts for the 3 memory tiers and stitches."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from .models import (
    Turn,
    FactItem,
    MemoryRecord,
    ExtractedMemoryPlan,
)


class BaseWorkingMemory(ABC):
    """Abstract interface for Tier 1: Working Memory (Fast Session Cache)."""

    @abstractmethod
    def append_turn(self, turn: Turn) -> None:
        """Append an ephemeral turn to the working session window."""
        pass

    @abstractmethod
    def get_active_window(self, session_id: str, limit: int = 10) -> List[Turn]:
        """Retrieve the most recent N turns for the given session."""
        pass

    @abstractmethod
    def get_session_turns(self, session_id: str) -> List[Turn]:
        """Retrieve all recorded turns for a session (e.g. for consolidation)."""
        pass

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Purge or reset working memory for a session."""
        pass


class BaseFactStore(ABC):
    """Abstract interface for Tier 2: Fact Store (Relational/Graph Structured Store)."""

    @abstractmethod
    def put_fact(self, fact: FactItem) -> FactItem:
        """Insert or update a fact with versioning tracking."""
        pass

    @abstractmethod
    def get_facts(self, user_id: str, active_only: bool = True, project_id: Optional[str] = None) -> List[FactItem]:
        """List facts belonging to a user, optionally filtered by project_id."""
        pass

    @abstractmethod
    def get_fact_by_key(
        self, user_id: str, key: str, active_only: bool = True, project_id: Optional[str] = None
    ) -> Optional[FactItem]:
        """Fetch a specific fact by key for a user, optionally filtered by project_id."""
        pass

    @abstractmethod
    def invalidate_fact(self, fact_id: UUID, superseded_by: Optional[UUID] = None) -> bool:
        """Mark a fact as inactive/superseded."""
        pass

    @abstractmethod
    def delete_fact(self, fact_id: UUID) -> bool:
        """Permanently delete a fact by ID."""
        pass

    @abstractmethod
    def update_fact(self, fact_id: UUID, new_value: str) -> Optional[FactItem]:
        """Directly update the value of an existing active fact."""
        pass

    @abstractmethod
    def invalidate_by_key(self, user_id: str, key: str, superseded_by: Optional[UUID] = None) -> int:
        """Mark all active facts matching the given key as inactive."""
        pass

    @abstractmethod
    def touch_fact(self, fact_id: UUID) -> None:
        """Update last_accessed_at and increment access count for soft decay."""
        pass


class BaseVectorStore(ABC):
    """Abstract interface for Tier 3: Semantic Vector Store."""

    @abstractmethod
    def upsert_vectors(self, records: List[MemoryRecord]) -> List[UUID]:
        """Upsert memory records with dense embeddings and metadata."""
        pass

    @abstractmethod
    def query_similar(
        self,
        user_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        active_only: bool = True,
        project_id: Optional[str] = None,
    ) -> List[MemoryRecord]:
        """Retrieve top-K semantically similar memories filtered by user, status, and project."""
        pass

    @abstractmethod
    def delete(self, record_id: UUID) -> bool:
        """Delete a vector record by UUID."""
        pass

    @abstractmethod
    def delete_by_user(self, user_id: str) -> int:
        """Delete all memories for a specific user."""
        pass


class BaseEmbedder(ABC):
    """Abstract interface for vector embedding generation."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate a dense vector embedding for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for a list of strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimension."""
        pass


class BaseLLMExtractor(ABC):
    """Abstract interface for Stitch 1: Triage & Fact Extraction."""

    @abstractmethod
    def extract_memory_plan(
        self,
        text: str,
        user_id: str,
        existing_facts: Optional[List[FactItem]] = None,
    ) -> ExtractedMemoryPlan:
        """Extract atomic facts, entities, and summaries from raw user input."""
        pass


class BaseGraphStore(ABC):
    """Abstract interface for Tier 4: Knowledge Graph Store (Memgraph / Neo4j / NetworkX)."""

    @abstractmethod
    def add_entity(
        self,
        user_id: str,
        name: str,
        entity_type: str = "Entity",
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> str:
        """Create or update an entity node in the graph."""
        pass

    @abstractmethod
    def add_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Create or update a directed relationship between two entities."""
        pass

    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query against the graph and return list of result dicts."""
        pass

    @abstractmethod
    def multi_hop_query(
        self,
        user_id: str,
        start_entity: str,
        relation: Optional[str] = None,
        hops: int = 2,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Traverse graph up to N hops from start entity following relations."""
        pass

    @abstractmethod
    def delete_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Remove a relationship between entities."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Check if graph backend is operational."""
        pass

