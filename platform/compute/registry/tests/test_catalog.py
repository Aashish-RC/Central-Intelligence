"""Unit tests for ModelCatalog (Task 16.3)."""

import pytest
from platform.compute.registry.model_catalog import (
    ModelCatalog,
    ModelEntry,
    ModelPricing,
)


@pytest.fixture
def catalog():
    return ModelCatalog()


def test_query_cheapest_model_supporting_vision(catalog: ModelCatalog):
    """Acceptance test: Can query cheapest model that supports vision."""
    # When looking at cloud models that support vision:
    # gemini-1.5-flash ($0.075 / $0.30) is cheaper than gpt-4o-mini ($0.15 / $0.60) and gpt-4o ($2.50)
    cheapest_cloud_vision = catalog.get_cheapest_model(capability="vision", cloud_only=True)
    assert cheapest_cloud_vision is not None
    assert cheapest_cloud_vision.model_id == "gemini-1.5-flash"
    assert "vision" in cheapest_cloud_vision.capabilities

    # If local models are included, zero-cost ollama/llama3.2-vision is cheapest
    cheapest_overall = catalog.get_cheapest_model(capability="vision", cloud_only=False)
    assert cheapest_overall is not None
    assert cheapest_overall.model_id == "ollama/llama3.2-vision"
    assert cheapest_overall.pricing.blended_cost_per_mtoken == 0.0


def test_health_aware_model_selection(catalog: ModelCatalog):
    """When the cheapest model becomes degraded or unavailable, failover to next cheapest."""
    # Degrade gemini-1.5-flash
    catalog.update_health("gemini-1.5-flash", "unavailable")

    cheapest_cloud = catalog.get_cheapest_model(capability="vision", healthy_only=True, cloud_only=True)
    assert cheapest_cloud is not None
    assert cheapest_cloud.model_id == "gpt-4o-mini"


def test_register_and_filter_custom_model(catalog: ModelCatalog):
    """Can register specialized custom model and query by criteria."""
    custom = ModelEntry(
        model_id="custom-finetune-sql",
        name="Internal SQL Fine-tune",
        provider="internal_vllm",
        capabilities={"code", "sql"},
        context_window=32768,
        pricing=ModelPricing(input_cost_per_mtoken=0.05, output_cost_per_mtoken=0.10),
        latency_p50_ms=90.0,
    )
    catalog.register_model(custom)

    found = catalog.find_models(capability="sql")
    assert len(found) == 1
    assert found[0].model_id == "custom-finetune-sql"
