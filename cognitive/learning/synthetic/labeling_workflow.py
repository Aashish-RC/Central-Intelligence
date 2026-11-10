"""Human-in-the-Loop Labeling Workflow (Feature 7.29)

Review queue enabling expert annotators to audit, refine, and approve
synthetic training examples before ingestion into model fine-tuning corpora.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from cognitive.learning.synthetic.data_generator import ExecutionRun, FineTuningExample


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


@dataclass
class ReviewItem:
    """An item placed in the labeling review queue."""
    review_id: str
    run: ExecutionRun
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: Optional[str] = None
    corrected_output: Optional[str] = None
    notes: str = ""
    timestamp: float = field(default_factory=time.time)


class LabelingWorkflowQueue:
    """Queue managing human verification and refinement of synthetic data."""

    def __init__(self) -> None:
        self.queue: Dict[str, ReviewItem] = {}

    def submit_for_review(self, run: ExecutionRun) -> str:
        """Submit an execution run for human review."""
        review_id = f"rev_{len(self.queue) + 1}_{run.run_id}"
        item = ReviewItem(review_id=review_id, run=run)
        self.queue[review_id] = item
        return review_id

    def review(
        self,
        review_id: str,
        reviewer: str,
        approved: bool,
        corrected_output: Optional[str] = None,
        notes: str = "",
    ) -> ReviewItem:
        """Record reviewer decision and optional corrections."""
        if review_id not in self.queue:
            raise KeyError(f"Review item {review_id} not found.")

        item = self.queue[review_id]
        item.reviewer = reviewer
        item.notes = notes

        if approved:
            if corrected_output:
                item.status = ReviewStatus.EDITED
                item.corrected_output = corrected_output
            else:
                item.status = ReviewStatus.APPROVED
        else:
            item.status = ReviewStatus.REJECTED

        return item

    def get_approved_examples(self) -> List[FineTuningExample]:
        """Harvest all human-approved and edited examples ready for fine-tuning."""
        examples: List[FineTuningExample] = []

        for item in self.queue.values():
            if item.status in [ReviewStatus.APPROVED, ReviewStatus.EDITED]:
                run = item.run
                output = item.corrected_output if item.status == ReviewStatus.EDITED else run.output_response
                messages = []
                if run.system_prompt:
                    messages.append({"role": "system", "content": run.system_prompt})
                messages.append({"role": "user", "content": run.input_prompt})
                messages.append({"role": "assistant", "content": output})

                examples.append(
                    FineTuningExample(
                        messages=messages,
                        metadata={
                            "review_id": item.review_id,
                            "reviewer": item.reviewer,
                            "status": item.status.value,
                        },
                    )
                )

        return examples

