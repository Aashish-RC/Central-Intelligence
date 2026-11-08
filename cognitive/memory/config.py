"""Configuration management for the Fused Dynamic Memory Layer."""

from enum import Enum
import os
from typing import Optional
from pydantic import BaseModel, Field


class WorkingMemoryBackend(str, Enum):
    IN_MEMORY = "in_memory"
    REDIS = "redis"


class FactStoreBackend(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class VectorStoreBackend(str, Enum):
    QDRANT = "qdrant"
    CHROMA = "chroma"


class EmbeddingBackend(str, Enum):
    LOCAL = "local"
    OPENAI = "openai"


class MemoryConfig(BaseModel):
    """Global configuration settings for Memory Layer."""

    # Working Memory (Tier 1)
    working_backend: WorkingMemoryBackend = Field(
        default=WorkingMemoryBackend.IN_MEMORY,
        description="Tier 1 backend: in_memory or redis",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Tier 1",
    )
    session_ttl_seconds: int = Field(
        default=3600 * 24,
        description="TTL for working session memory (seconds)",
    )
    wal_dir: str = Field(
        default="./wal",
        description="Directory for local Write-Ahead Log in Tier 1",
    )

    # Fact Store (Tier 2)
    fact_backend: FactStoreBackend = Field(
        default=FactStoreBackend.SQLITE,
        description="Tier 2 backend: sqlite or postgres",
    )
    sqlite_path: str = Field(
        default="./facts.db",
        description="SQLite database path for Tier 2",
    )
    postgres_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string for Tier 2",
    )

    # Vector Store (Tier 3)
    vector_backend: VectorStoreBackend = Field(
        default=VectorStoreBackend.QDRANT,
        description="Tier 3 backend: qdrant or chroma",
    )
    qdrant_location: str = Field(
        default=":memory:",
        description="Qdrant location: ':memory:', local path, or URL",
    )
    chroma_path: str = Field(
        default="./chroma_db",
        description="Chroma persistent storage directory",
    )
    collection_name: str = Field(
        default="agent_memories",
        description="Collection name for semantic vector storage",
    )

    # Embeddings
    embedding_backend: EmbeddingBackend = Field(
        default=EmbeddingBackend.LOCAL,
        description="Embedding provider: local or openai",
    )
    embedding_dim: int = Field(
        default=384,
        description="Embedding vector dimensionality",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API Key for embeddings / extraction",
    )
    openai_base_url: Optional[str] = Field(
        default=None,
        description="Custom base URL for OpenAI-compatible endpoint",
    )

    # Context Synthesizer & Token Budgets
    max_context_tokens: int = Field(
        default=500,
        description="Maximum token budget for synthesized context injection",
    )
    working_window_turns: int = Field(
        default=6,
        description="Number of most recent conversation turns in Tier 1 context",
    )
    top_k_semantic_matches: int = Field(
        default=4,
        description="Number of semantic vector memories to recall in Tier 3",
    )

    # Fact Decay & Scoring
    decay_half_life_days: float = Field(
        default=14.0,
        description="Half-life in days for fact relevance decay",
    )

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        """Instantiate config with overrides from environment variables."""
        return cls(
            working_backend=os.getenv("MEMORY_WORKING_BACKEND", WorkingMemoryBackend.IN_MEMORY.value),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "86400")),
            wal_dir=os.getenv("WAL_DIR", "./wal"),
            fact_backend=os.getenv("MEMORY_FACT_BACKEND", FactStoreBackend.SQLITE.value),
            sqlite_path=os.getenv("SQLITE_PATH", "./facts.db"),
            postgres_url=os.getenv("POSTGRES_URL"),
            vector_backend=os.getenv("MEMORY_VECTOR_BACKEND", VectorStoreBackend.QDRANT.value),
            qdrant_location=os.getenv("QDRANT_LOCATION", ":memory:"),
            chroma_path=os.getenv("CHROMA_PATH", "./chroma_db"),
            collection_name=os.getenv("COLLECTION_NAME", "agent_memories"),
            embedding_backend=os.getenv("MEMORY_EMBEDDING_BACKEND", EmbeddingBackend.LOCAL.value),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "384")),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            max_context_tokens=int(os.getenv("MAX_CONTEXT_TOKENS", "500")),
            working_window_turns=int(os.getenv("WORKING_WINDOW_TURNS", "6")),
            top_k_semantic_matches=int(os.getenv("TOP_K_SEMANTIC_MATCHES", "4")),
            decay_half_life_days=float(os.getenv("DECAY_HALF_LIFE_DAYS", "14.0")),
        )


# Global default config singleton
default_config = MemoryConfig.from_env()
