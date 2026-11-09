"""Tests for Evaluation Datasets, Custom Scorers, and Golden Suites (Task 11.3)."""

import pytest
from pathlib import Path
from control.evaluation.datasets.custom_scorer import (
    CompositeScorer,
    ContainsAllScorer,
    ExactMatchScorer,
    JsonSchemaScorer,
    RegexScorer,
)
from control.evaluation.datasets.dataset_store import (
    DatasetSample,
    DatasetStore,
    EvaluationDataset,
)
from control.evaluation.datasets.golden_suites import (
    GoldenSuite,
    GoldenSuiteRunner,
)


def test_custom_scorers():
    """Validates individual custom scorer implementations."""
    # 1. Exact match
    em = ExactMatchScorer(case_sensitive=False)
    assert em.score("Hello World", "hello world").passed is True
    assert em.score("Hello", "World").passed is False

    # 2. Contains all
    contains = ContainsAllScorer(required_terms=["python", "async"])
    res1 = contains.score("Python with async/await support")
    assert res1.passed is True
    assert res1.score == 1.0

    res2 = contains.score("Python only")
    assert res2.passed is False
    assert res2.score == 0.5

    # 3. Regex
    regex_scorer = RegexScorer(r"^Task-\d{3}: completed")
    assert regex_scorer.score("Task-101: completed successfully").passed is True
    assert regex_scorer.score("Task failed").passed is False

    # 4. JSON Schema
    json_scorer = JsonSchemaScorer(required_keys=["status", "data"])
    assert json_scorer.score('{"status": "ok", "data": [1, 2]}').passed is True
    assert json_scorer.score('{"status": "ok"}').passed is False
    assert json_scorer.score("not a json").passed is False

    # 5. Composite
    comp = CompositeScorer([
        (ExactMatchScorer(case_sensitive=False), 0.5),
        (ContainsAllScorer(required_terms=["gold"]), 0.5),
    ], pass_threshold=0.8)

    assert comp.score("gold", "gold").passed is True
    assert comp.score("silver", "gold").passed is False


def test_dataset_store_crud(tmp_path: Path):
    """Verifies dataset store CRUD, domain queries, and persistence."""
    store = DatasetStore(storage_dir=tmp_path)

    sample1 = DatasetSample(
        sample_id="S1",
        input_prompt="What is AI?",
        expected_output="Artificial Intelligence",
        domain="tech",
    )
    sample2 = DatasetSample(
        sample_id="S2",
        input_prompt="What is GDP?",
        expected_output="Gross Domestic Product",
        domain="finance",
    )

    ds1 = store.create_dataset(
        dataset_id="ds-tech",
        name="Tech QA",
        domain="tech",
        samples=[sample1],
    )
    store.create_dataset(
        dataset_id="ds-finance",
        name="Finance QA",
        domain="finance",
        samples=[sample2],
    )

    assert store.get_dataset("ds-tech") is not None
    assert len(store.list_datasets()) == 2
    assert len(store.list_datasets(domain="tech")) == 1
    assert store.list_datasets(domain="tech")[0].samples[0].sample_id == "S1"

    # Persistence verification
    store2 = DatasetStore(storage_dir=tmp_path)
    assert store2.get_dataset("ds-finance") is not None

    # Delete
    assert store.delete_dataset("ds-tech") is True
    assert store.get_dataset("ds-tech") is None


def test_golden_suite_runner_acceptance():
    """Acceptance Test: Can create a golden suite, run it against a model, get pass/fail."""
    dataset = EvaluationDataset(
        dataset_id="golden-core-1",
        name="Core Capabilities",
        domain="core",
        samples=[
            DatasetSample(sample_id="G1", input_prompt="Capital of France?", expected_output="Paris", domain="core"),
            DatasetSample(sample_id="G2", input_prompt="Capital of Japan?", expected_output="Tokyo", domain="core"),
            DatasetSample(sample_id="G3", input_prompt="Capital of Germany?", expected_output="Berlin", domain="core"),
        ],
    )

    suite = GoldenSuite(
        suite_id="golden-v1",
        name="Geography Core Golden Suite",
        datasets=[dataset],
        pass_threshold=0.66,
    )

    runner = GoldenSuiteRunner(suite)

    # 1. High accuracy model passes
    accurate_model = lambda prompt: "Paris" if "France" in prompt else ("Tokyo" if "Japan" in prompt else "Berlin")
    report1 = runner.run(accurate_model)
    assert report1.passed is True
    assert report1.pass_rate == 1.0
    assert report1.total_samples == 3
    assert len(report1.failures) == 0

    # 2. Deficient model fails threshold
    deficient_model = lambda prompt: "London"
    report2 = runner.run(deficient_model)
    assert report2.passed is False
    assert report2.pass_rate == 0.0
    assert len(report2.failures) == 3

