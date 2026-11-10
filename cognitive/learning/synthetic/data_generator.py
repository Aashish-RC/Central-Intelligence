"""Synthetic Dataset Generator (Features 7.28, 7.29)

Harvests high-performing agent execution runs and transforms them into standardized
JSONL fine-tuning datasets (ChatML / OpenAI / Gemini formatted) with dataset augmentation.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRun:
    """Historical run of an agent execution."""
    run_id: str
    system_prompt: str
    input_prompt: str
    output_response: str
    success: bool = True
    quality_score: float = 1.0  # 0.0 to 1.0
    user_rating: Optional[int] = None  # e.g., 1 (positive), -1 (negative)
    tools_called: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FineTuningExample:
    """Chat-formatted training example."""
    messages: List[Dict[str, str]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"messages": self.messages}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class SyntheticDatasetGenerator:
    """Collects and transforms agent trajectory runs into fine-tuning datasets."""

    def __init__(self) -> None:
        self.runs: Dict[str, ExecutionRun] = {}

    def ingest_run(self, run: ExecutionRun) -> None:
        """Register an execution run in the generator repository."""
        self.runs[run.run_id] = run

    def filter_successful_runs(
        self,
        min_quality: float = 0.75,
        require_success: bool = True,
        min_rating: Optional[int] = None,
    ) -> List[ExecutionRun]:
        """Filter runs satisfying quality and success thresholds."""
        results: List[ExecutionRun] = []
        for run in self.runs.values():
            if require_success and not run.success:
                continue
            if run.quality_score < min_quality:
                continue
            if min_rating is not None and (run.user_rating is None or run.user_rating < min_rating):
                continue
            results.append(run)
        return results

    def convert_to_fine_tuning_example(self, run: ExecutionRun) -> FineTuningExample:
        """Transform a successful run into standard conversational JSONL training example."""
        messages: List[Dict[str, str]] = []
        if run.system_prompt:
            messages.append({"role": "system", "content": run.system_prompt})
        messages.append({"role": "user", "content": run.input_prompt})
        messages.append({"role": "assistant", "content": run.output_response})

        return FineTuningExample(
            messages=messages,
            metadata={"run_id": run.run_id, "quality_score": run.quality_score},
        )

    def export_jsonl(
        self,
        runs: Optional[List[ExecutionRun]] = None,
        min_quality: float = 0.75,
    ) -> str:
        """Export candidate runs as a serialized JSONL dataset string."""
        target_runs = runs if runs is not None else self.filter_successful_runs(min_quality=min_quality)
        lines: List[str] = []

        for run in target_runs:
            example = self.convert_to_fine_tuning_example(run)
            lines.append(example.to_json())

        return "\n".join(lines)
