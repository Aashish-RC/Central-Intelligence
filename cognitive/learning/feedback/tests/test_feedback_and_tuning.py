"""Tests for L7 Learning feedback signals (A7.1-A7.4) and tuning pipelines (A7.5-A7.6)."""

from pathlib import Path

import pytest

from cognitive.learning.feedback import (
    AcceptanceAction,
    AcceptanceTracker,
    ImplicitSignalTracker,
    NPSSurveyManager,
    RatingsStore,
)
from cognitive.learning.tuning import (
    FullFineTuningOrchestrator,
    FullTuneConfig,
    LoRAConfig,
    PEFTTrainer,
    TrainingExample,
)


def test_l7_feedback_suite():
    acc = AcceptanceTracker()
    acc.record("r1", "u1", AcceptanceAction.USE_THIS, model_id="m1")
    acc.record("r2", "u1", AcceptanceAction.COPY, model_id="m1")
    acc.record("r3", "u1", AcceptanceAction.DISMISS, model_id="m1")
    assert acc.get_stats("m1").acceptance_rate == round(2 / 3, 4)

    ratings = RatingsStore()
    ratings.add_rating("r1", "u1", 5, model_id="m1")
    ratings.add_rating("r2", "u2", 4, model_id="m1")
    agg = ratings.aggregate("m1")
    assert agg.average_stars == 4.5
    assert agg.distribution[5] == 1

    imp = ImplicitSignalTracker()
    imp.record_signal("r1", "u1", reading_time_ms=25000.0, scroll_depth_pct=90.0, copy_count=1)
    summary = imp.summarize_response("r1")
    assert summary.engagement_score > 0.7

    nps = NPSSurveyManager(cooldown_seconds=3600.0)
    assert nps.deliver_prompt("u1", now=1000.0)["delivered"] is True
    assert nps.deliver_prompt("u1", now=1200.0)["delivered"] is False
    nps.record_response("u1", 10)  # promoter
    nps.record_response("u2", 9)   # promoter
    nps.record_response("u3", 5)   # detractor
    breakdown = nps.aggregate_nps()
    assert breakdown.promoters == 2 and breakdown.detractors == 1
    assert breakdown.nps_score == round(((2 - 1) / 3) * 100.0, 2)


def test_l7_peft_lora_and_full_tuning(tmp_path: Path):
    examples = [TrainingExample(prompt=f"Q{i}", completion=f"A{i}") for i in range(100)]
    trainer = PEFTTrainer()
    adapter = trainer.train(examples, LoRAConfig(base_model="llama-3.1-8b", rank=16), output_dir=tmp_path)
    assert adapter.example_count == 100
    assert adapter.trainable_params > 0
    assert (Path(adapter.artifact_dir) / "adapter_config.json").exists()

    orch = FullFineTuningOrchestrator()
    with pytest.raises(ValueError):
        FullTuneConfig(base_model="llama-3.1-8b", params_billions=8.0, dataset_size=50)
    job = orch.configure_job(FullTuneConfig(base_model="llama-3.1-8b", params_billions=8.0, dataset_size=2000, num_gpus=8))
    assert job.status == "configured"
    assert job.total_steps > 0

