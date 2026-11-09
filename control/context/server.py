"""FastAPI HTTP service for Context Engineering (Layer 9)."""

from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from control.context.assembly.context_assembler import (
    ContextAssembler,
    TokenBudgetConfig,
    AssembledContext,
)

app = FastAPI(
    title="Layer 9 Context Engineering API",
    description="Context assembly, dual-boundary prompt defense, and cache prefix optimization.",
    version="1.0.0",
)

_assembler = ContextAssembler()


class AssembleContextRequest(BaseModel):
    system_instructions: Optional[str] = None
    memory_records: Optional[List[Union[Dict[str, Any], str]]] = None
    retrieved_knowledge: Optional[List[Union[Dict[str, Any], str]]] = None
    active_tools: Optional[List[Union[Dict[str, Any], str]]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    situational_context: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    budget_config: Optional[Dict[str, int]] = None


class AssembleContextResponse(BaseModel):
    system_prompt: str
    memory_context: str
    knowledge_context: str
    tools_context: str
    conversation_context: str
    full_prompt: str
    token_counts: Dict[str, int]
    total_tokens: int
    sources_included: List[str]
    pruned: bool
    compacted: bool
    strategy_used: str
    metadata: Dict[str, Any]


@app.post("/v1/context/assemble", response_model=AssembleContextResponse)
async def assemble_context(req: AssembleContextRequest) -> AssembleContextResponse:
    """Assembles unified context bounded by token budget across all cognitive tiers."""
    assembler = _assembler
    if req.budget_config:
        config = TokenBudgetConfig(
            total_budget=req.budget_config.get("total_budget", 4096),
            system_budget=req.budget_config.get("system_budget", 600),
            memory_budget=req.budget_config.get("memory_budget", 800),
            knowledge_budget=req.budget_config.get("knowledge_budget", 1200),
            tools_budget=req.budget_config.get("tools_budget", 500),
            conversation_budget=req.budget_config.get("conversation_budget", 1000),
            situational_budget=req.budget_config.get("situational_budget", 200),
        )
        assembler = ContextAssembler(config=config)

    result = assembler.assemble(
        system_instructions=req.system_instructions,
        memory_records=req.memory_records,
        retrieved_knowledge=req.retrieved_knowledge,
        active_tools=req.active_tools,
        conversation_history=req.conversation_history,
        situational_context=req.situational_context,
        user_id=req.user_id,
        session_id=req.session_id,
    )

    return AssembleContextResponse(
        system_prompt=result.system_prompt,
        memory_context=result.memory_context,
        knowledge_context=result.knowledge_context,
        tools_context=result.tools_context,
        conversation_context=result.conversation_context,
        full_prompt=result.full_prompt,
        token_counts=result.token_counts,
        total_tokens=result.total_tokens,
        sources_included=result.sources_included,
        pruned=result.pruned,
        compacted=result.compacted,
        strategy_used=result.strategy_used.value,
        metadata=result.metadata,
    )
