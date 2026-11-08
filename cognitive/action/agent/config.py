"""Unified Environmental & Feature Configurations for the Agent Layer."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class AgentLayerConfig(BaseModel):
    """Runtime configuration for Agent Layer services."""

    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8002")))
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))

    # Model Gateway Integration
    model_gateway_url: str = Field(
        default_factory=lambda: os.getenv("MODEL_GATEWAY_URL", "http://localhost:8000")
    )
    default_model: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
    )

    # Fused Memory Integration
    memory_service_url: str = Field(
        default_factory=lambda: os.getenv("MEMORY_SERVICE_URL", "http://localhost:8001")
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    qdrant_host: str = Field(
        default_factory=lambda: os.getenv("QDRANT_HOST", "localhost")
    )
    qdrant_port: int = Field(
        default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333"))
    )
    sqlite_db_path: str = Field(
        default_factory=lambda: os.getenv("SQLITE_DB_PATH", str(Path.home() / ".pheonix" / "agent_facts.db"))
    )

    # Sandbox Configuration
    sandbox_provider: str = Field(
        default_factory=lambda: os.getenv("SANDBOX_PROVIDER", "local")
    )  # "e2b" or "local"
    e2b_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("E2B_API_KEY", None)
    )
    sandbox_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "60"))
    )

    # Guardrails Configuration
    guardrail_provider: str = Field(
        default_factory=lambda: os.getenv("GUARDRAIL_PROVIDER", "parlant")
    )
    parlant_api_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("PARLANT_API_URL", None)
    )

    # LiveKit Voice Configuration
    livekit_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("LIVEKIT_URL", None)
    )
    livekit_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("LIVEKIT_API_KEY", None)
    )
    livekit_api_secret: Optional[str] = Field(
        default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", None)
    )


default_config = AgentLayerConfig()
