"""FastAPI REST application exposing the Fused Dynamic Memory Layer."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from memory.engine import MemoryEngine
from memory.core.models import ContextPackage, TurnRole


app = FastAPI(
    title="Pheonix Fused Dynamic Memory Layer",
    description="3-Tier cognitive memory layer for AI agents with automated fact extraction, conflict resolution, and token synthesis.",
    version="0.1.0",
)

# Engine singleton for API server
engine = MemoryEngine()


class RememberRequest(BaseModel):
    user_id: str = Field(..., description="User or agent ID")
    text: str = Field(..., description="Message text or agent action to remember")
    session_id: Optional[str] = Field(default=None, description="Active session ID")
    role: TurnRole = Field(default=TurnRole.USER, description="Message speaker role")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata attributes")


class RecallRequest(BaseModel):
    user_id: str = Field(..., description="User or agent ID")
    query: str = Field(..., description="Natural language recall query")
    session_id: Optional[str] = Field(default=None, description="Active session ID for working buffer")
    top_k: Optional[int] = Field(default=None, description="Number of semantic matches")


class ConsolidateRequest(BaseModel):
    user_id: str = Field(..., description="User or agent ID")
    session_id: str = Field(..., description="Session ID to consolidate and purge")


@app.get("/health")
def health_check():
    """Health check reporting system and backend status."""
    return {
        "status": "healthy",
        "working_tier": engine.config.working_backend.value,
        "facts_tier": engine.config.fact_backend.value,
        "semantic_tier": engine.config.vector_backend.value,
        "max_context_tokens": engine.config.max_context_tokens,
    }


@app.post("/api/v1/remember")
def remember_interaction(req: RememberRequest):
    """Record an interaction, extract atomic facts, resolve contradictions, and store vector memory."""
    try:
        res = engine.remember(
            user_id=req.user_id,
            text=req.text,
            session_id=req.session_id,
            role=req.role,
            metadata=req.metadata,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recall", response_model=ContextPackage)
def recall_context(req: RecallRequest):
    """Retrieve concentrated context (< 500 tokens) synthesized across the 3 tiers."""
    try:
        package = engine.recall(
            user_id=req.user_id,
            query=req.query,
            session_id=req.session_id,
            top_k=req.top_k,
        )
        return package
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/facts/{user_id}")
def get_user_facts(user_id: str):
    """Retrieve all active ground-truth structured facts for a user."""
    try:
        facts = engine.get_active_facts(user_id=user_id)
        return {"user_id": user_id, "active_facts": [f.model_dump() for f in facts]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/consolidate")
def consolidate_session(req: ConsolidateRequest):
    """Trigger REM sleep consolidation for a completed session."""
    try:
        res = engine.consolidate(user_id=req.user_id, session_id=req.session_id)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
