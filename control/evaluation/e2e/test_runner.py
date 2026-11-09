"""Unified End-to-End Pipeline Test Runner (Layer 11: Evaluation & Quality, Feature 11.05).

Coordinates cross-layer end-to-end tests exercising L1->L2->L3->L4->L5->L6->L8 pipeline continuity.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("control.evaluation.e2e")


class PipelineStage(str, Enum):
    L1_GATEWAY = "L1_Gateway"
    L2_MEMORY = "L2_Memory"
    L3_KNOWLEDGE = "L3_Knowledge"
    L4_REASONING = "L4_Reasoning"
    L5_ACTION = "L5_Action"
    L6_COLLABORATION = "L6_Collaboration"
    L8_ORCHESTRATION = "L8_Orchestration"


@dataclass
class StageExecutionResult:
    """Execution telemetry for an individual pipeline stage."""
    stage: PipelineStage
    success: bool
    input_payload: Any
    output_payload: Any
    duration_ms: float
    error: Optional[str] = None


@dataclass
class E2EPipelineRun:
    """Aggregated outcome of an end-to-end pipeline run."""
    run_id: str
    overall_success: bool
    stages: List[StageExecutionResult]
    total_duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_stage_result(self, stage: PipelineStage) -> Optional[StageExecutionResult]:
        for s in self.stages:
            if s.stage == stage:
                return s
        return None


class UnifiedE2ETestRunner:
    """End-to-end integration test runner validating pipeline continuity across Central-Intelligence layers."""

    def __init__(self, stage_handlers: Optional[Dict[PipelineStage, Callable[[Any], Any]]] = None):
        self.stage_handlers = stage_handlers or {}

    def register_stage(self, stage: PipelineStage, handler: Callable[[Any], Any]) -> None:
        self.stage_handlers[stage] = handler

    def execute_pipeline(self, initial_request: Dict[str, Any]) -> E2EPipelineRun:
        """Executes full sequence L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L8."""
        run_id = f"e2e-{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        pipeline_order = [
            PipelineStage.L1_GATEWAY,
            PipelineStage.L2_MEMORY,
            PipelineStage.L3_KNOWLEDGE,
            PipelineStage.L4_REASONING,
            PipelineStage.L5_ACTION,
            PipelineStage.L6_COLLABORATION,
            PipelineStage.L8_ORCHESTRATION,
        ]

        stages: List[StageExecutionResult] = []
        current_payload = dict(initial_request)
        overall_success = True

        for stage in pipeline_order:
            s_start = time.perf_counter()
            handler = self.stage_handlers.get(stage, self._default_handler_for(stage))

            try:
                stage_output = handler(current_payload)
                s_dur = (time.perf_counter() - s_start) * 1000.0
                stages.append(
                    StageExecutionResult(
                        stage=stage,
                        success=True,
                        input_payload=current_payload,
                        output_payload=stage_output,
                        duration_ms=s_dur,
                    )
                )
                # Pass forward merged context
                if isinstance(stage_output, dict):
                    current_payload.update(stage_output)
                else:
                    current_payload[f"{stage.value}_output"] = stage_output

            except Exception as exc:
                s_dur = (time.perf_counter() - s_start) * 1000.0
                stages.append(
                    StageExecutionResult(
                        stage=stage,
                        success=False,
                        input_payload=current_payload,
                        output_payload=None,
                        duration_ms=s_dur,
                        error=str(exc),
                    )
                )
                overall_success = False
                break

        total_dur = (time.perf_counter() - t_start) * 1000.0
        return E2EPipelineRun(
            run_id=run_id,
            overall_success=overall_success,
            stages=stages,
            total_duration_ms=total_dur,
        )

    def _default_handler_for(self, stage: PipelineStage) -> Callable[[Any], Any]:
        """Provides default stage mock handling when not overridden."""
        def l1_gateway(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"authenticated": True, "user_id": p.get("user_id", "user_101")}

        def l2_memory(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"recalled_memories": ["Prefers concise answers", "Prior project: Project Apollo"]}

        def l3_knowledge(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"retrieved_docs": ["Doc #42: Project Apollo architecture specification"]}

        def l4_reasoning(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"plan": "Synthesize specification details with concise delivery format"}

        def l5_action(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"action_executed": "tool:generate_summary", "action_status": "success"}

        def l6_collab(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"delegation_verified": True, "peer_acknowledgement": "acknowledged"}

        def l8_orch(p: Dict[str, Any]) -> Dict[str, Any]:
            return {"final_response": "Apollo architecture summary generated and validated.", "routed_model": "claude-3-7-sonnet"}

        mapping = {
            PipelineStage.L1_GATEWAY: l1_gateway,
            PipelineStage.L2_MEMORY: l2_memory,
            PipelineStage.L3_KNOWLEDGE: l3_knowledge,
            PipelineStage.L4_REASONING: l4_reasoning,
            PipelineStage.L5_ACTION: l5_action,
            PipelineStage.L6_COLLABORATION: l6_collab,
            PipelineStage.L8_ORCHESTRATION: l8_orch,
        }
        return mapping[stage]
