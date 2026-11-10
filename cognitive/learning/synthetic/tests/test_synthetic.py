"""Unit tests for Synthetic Dataset Generator & Labeling Workflow (Features 7.28, 7.29)."""

import json
import pytest
from cognitive.learning.synthetic.data_generator import (
    SyntheticDatasetGenerator,
    ExecutionRun,
)
from cognitive.learning.synthetic.labeling_workflow import (
    LabelingWorkflowQueue,
    ReviewStatus,
)


def test_can_export_100_runs_as_jsonl_fine_tuning_dataset():
    generator = SyntheticDatasetGenerator()

    # Ingest 100 successful runs
    for i in range(1, 101):
        run = ExecutionRun(
            run_id=f"run_{i:03d}",
            system_prompt="You are Central Intelligence assistant.",
            input_prompt=f"Execute query operation {i} with deterministic parameters.",
            output_response=f"Operation {i} successfully completed with status 200 OK.",
            success=True,
            quality_score=0.92,
            user_rating=1,
        )
        generator.ingest_run(run)

    # Ingest 5 failed runs that should be filtered out
    for j in range(1, 6):
        bad_run = ExecutionRun(
            run_id=f"bad_run_{j}",
            system_prompt="",
            input_prompt="Corrupted prompt",
            output_response="Error encountered",
            success=False,
            quality_score=0.2,
        )
        generator.ingest_run(bad_run)

    jsonl_output = generator.export_jsonl(min_quality=0.8)
    lines = [line for line in jsonl_output.strip().split("\n") if line.strip()]

    # Exactly 100 runs exported
    assert len(lines) == 100

    # Parse first line to verify JSONL structure
    first_record = json.loads(lines[0])
    assert "messages" in first_record
    assert len(first_record["messages"]) == 3
    assert first_record["messages"][0]["role"] == "system"
    assert first_record["messages"][1]["role"] == "user"
    assert first_record["messages"][2]["role"] == "assistant"
    assert "Operation 1 successfully completed" in first_record["messages"][2]["content"]


def test_labeling_workflow_review_and_approval():
    queue = LabelingWorkflowQueue()

    run = ExecutionRun(
        run_id="run_eval_01",
        system_prompt="You are a legal summarizer.",
        input_prompt="Summarize clause 4.",
        output_response="Clause 4 states liability is limited.",
        quality_score=0.7,
    )

    review_id = queue.submit_for_review(run)
    assert review_id in queue.queue

    # Reviewer edits and approves
    item = queue.review(
        review_id=review_id,
        reviewer="lead_evaluator",
        approved=True,
        corrected_output="Clause 4 stipulates total liability is capped at aggregate fees paid in prior 12 months.",
        notes="Added exact monetary limit specification.",
    )

    assert item.status == ReviewStatus.EDITED
    assert item.reviewer == "lead_evaluator"

    approved = queue.get_approved_examples()
    assert len(approved) == 1
    assert "aggregate fees paid" in approved[0].messages[-1]["content"]

