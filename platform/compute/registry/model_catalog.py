"""Model Registry & Catalog (L16 Compute - Tasks 16.22-16.26).

Central registry of all available AI model variants across local and cloud
providers, cataloging capabilities (vision, audio, tools, json), context limits,
pricing per million tokens, and live operational health.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    VISION = "vision"
    AUDIO = "audio"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"
    CODE = "code"
    EXTENDED_THINKING = "extended_thinking"
    EMBEDDINGS = "embeddings"


@dataclass
class ModelPricing:
    """Pricing in USD per 1M tokens."""
    input_cost_per_mtoken: float = 0.0
    output_cost_per_mtoken: float = 0.0

    @property
    def blended_cost_per_mtoken(self) -> float:
        """Standard 3:1 input-to-output blended estimate."""
        return (self.input_cost_per_mtoken * 0.75) + (self.output_cost_per_mtoken * 0.25)


@dataclass
class ModelEntry:
    """Detailed metadata for a model variant."""
    model_id: str
    name: str
    provider: str
    capabilities: Set[str] = field(default_factory=set)
    context_window: int = 128000
    pricing: ModelPricing = field(default_factory=ModelPricing)
    health_status: str = "healthy"  # "healthy", "degraded", "unavailable"
    latency_p50_ms: float = 450.0
    is_local: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelCatalog:
    """Queryable registry of model offerings."""

    def __init__(self) -> None:
        self._models: Dict[str, ModelEntry] = {}
        self._seed_default_models()

    def _seed_default_models(self) -> None:
        """Seed registry with common modern models."""
        defaults = [
            ModelEntry(
                model_id="gpt-4o",
                name="OpenAI GPT-4o",
                provider="openai",
                capabilities={"vision", "function_calling", "json_mode", "code"},
                context_window=128000,
                pricing=ModelPricing(input_cost_per_mtoken=2.50, output_cost_per_mtoken=10.00),
                health_status="healthy",
                latency_p50_ms=480.0,
            ),
            ModelEntry(
                model_id="gpt-4o-mini",
                name="OpenAI GPT-4o Mini",
                provider="openai",
                capabilities={"vision", "function_calling", "json_mode", "code"},
                context_window=128000,
                pricing=ModelPricing(input_cost_per_mtoken=0.15, output_cost_per_mtoken=0.60),
                health_status="healthy",
                latency_p50_ms=250.0,
            ),
            ModelEntry(
                model_id="claude-3-7-sonnet",
                name="Anthropic Claude 3.7 Sonnet",
                provider="anthropic",
                capabilities={"vision", "function_calling", "code", "extended_thinking"},
                context_window=200000,
                pricing=ModelPricing(input_cost_per_mtoken=3.00, output_cost_per_mtoken=15.00),
                health_status="healthy",
                latency_p50_ms=520.0,
            ),
            ModelEntry(
                model_id="gemini-1.5-flash",
                name="Google Gemini 1.5 Flash",
                provider="google",
                capabilities={"vision", "audio", "function_calling", "json_mode", "code"},
                context_window=1000000,
                pricing=ModelPricing(input_cost_per_mtoken=0.075, output_cost_per_mtoken=0.30),
                health_status="healthy",
                latency_p50_ms=200.0,
            ),
            ModelEntry(
                model_id="deepseek-v3",
                name="DeepSeek V3",
                provider="deepseek",
                capabilities={"code", "json_mode", "function_calling"},
                context_window=64000,
                pricing=ModelPricing(input_cost_per_mtoken=0.14, output_cost_per_mtoken=0.28),
                health_status="healthy",
                latency_p50_ms=400.0,
            ),
            ModelEntry(
                model_id="ollama/llama3.2-vision",
                name="Ollama LLaMA 3.2 11B Vision",
                provider="ollama",
                capabilities={"vision", "code"},
                context_window=128000,
                pricing=ModelPricing(input_cost_per_mtoken=0.0, output_cost_per_mtoken=0.0),
                health_status="healthy",
                is_local=True,
                latency_p50_ms=120.0,
            ),
        ]
        for m in defaults:
            self._models[m.model_id] = m

    def register_model(self, entry: ModelEntry) -> None:
        """Register or update model entry."""
        self._models[entry.model_id] = entry
        logger.info("Registered model in catalog: %s (%s)", entry.model_id, entry.provider)

    def get_model(self, model_id: str) -> Optional[ModelEntry]:
        """Fetch model by ID."""
        return self._models.get(model_id)

    def update_health(self, model_id: str, status: str) -> bool:
        """Update operational status for a model."""
        if model_id in self._models:
            self._models[model_id].health_status = status
            return True
        return False

    def find_models(
        self,
        capability: Optional[str] = None,
        max_input_price: Optional[float] = None,
        min_context: Optional[int] = None,
        provider: Optional[str] = None,
        healthy_only: bool = True,
        cloud_only: bool = False,
    ) -> List[ModelEntry]:
        """Query matching models based on criteria."""
        results = []
        for model in self._models.values():
            if healthy_only and model.health_status != "healthy":
                continue
            if cloud_only and model.is_local:
                continue
            if provider and model.provider != provider:
                continue
            if capability and capability not in model.capabilities:
                continue
            if max_input_price is not None and model.pricing.input_cost_per_mtoken > max_input_price:
                continue
            if min_context is not None and model.context_window < min_context:
                continue
            results.append(model)
        return results

    def get_cheapest_model(
        self,
        capability: Optional[str] = None,
        healthy_only: bool = True,
        cloud_only: bool = False,
    ) -> Optional[ModelEntry]:
        """Return the lowest blended cost model supporting requested capability."""
        candidates = self.find_models(
            capability=capability,
            healthy_only=healthy_only,
            cloud_only=cloud_only,
        )
        if not candidates:
            return None

        # Sort by blended cost, then input price
        candidates.sort(
            key=lambda m: (m.pricing.blended_cost_per_mtoken, m.pricing.input_cost_per_mtoken)
        )
        return candidates[0]
