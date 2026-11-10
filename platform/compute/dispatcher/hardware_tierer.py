"""Dynamic Hardware Auto-Tiering Dispatcher (L16 Compute - Tasks 16.07, 16.17).

Evaluates system GPU availability, free VRAM, battery level, and model size to
dynamically route inference requests between local hardware (Ollama / on-device)
and cloud infrastructure (vLLM / managed model APIs).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ComputeTarget(str, Enum):
    """Target compute provider / execution host."""
    LOCAL_OLLAMA = "local_ollama"
    CLOUD_VLLM = "cloud_vllm"
    CLOUD_API = "cloud_api"


@dataclass
class HardwareProfile:
    """Current snapshot of host machine hardware telemetry."""
    gpu_available: bool = False
    vram_free_gb: float = 0.0
    battery_pct: float = 100.0  # 0 to 100
    is_plugged_in: bool = True
    gpu_name: Optional[str] = None


class HardwareTierDispatcher:
    """Dispatches model inference requests based on live hardware profile and model weight size."""

    def __init__(self, min_battery_threshold: float = 20.0, vram_headroom_ratio: float = 1.5) -> None:
        self.min_battery_threshold = min_battery_threshold
        self.vram_headroom_ratio = vram_headroom_ratio

    def route(
        self,
        task: Any,
        model_size_gb: float,
        gpu_available: bool,
        vram_free_gb: float,
        battery_pct: float,
        prefer_local: bool = True,
    ) -> ComputeTarget:
        """Route task to local or cloud target.

        Algorithm:
        - If GPU available and free VRAM > model_size * 1.5 and battery > 20%:
            return LOCAL_OLLAMA
        - Else:
            return CLOUD_VLLM
        """
        if prefer_local and gpu_available and (vram_free_gb >= model_size_gb * self.vram_headroom_ratio):
            if battery_pct > self.min_battery_threshold:
                logger.info(
                    "Routing task to LOCAL_OLLAMA (model=%.1fGB, vram_free=%.1fGB, battery=%.1f%%)",
                    model_size_gb,
                    vram_free_gb,
                    battery_pct,
                )
                return ComputeTarget.LOCAL_OLLAMA
            else:
                logger.warning(
                    "Local GPU capable but battery too low (%.1f%% <= %.1f%%). Offloading to cloud.",
                    battery_pct,
                    self.min_battery_threshold,
                )

        logger.info(
            "Routing task to CLOUD_VLLM (model=%.1fGB, vram_free=%.1fGB, gpu=%s)",
            model_size_gb,
            vram_free_gb,
            gpu_available,
        )
        return ComputeTarget.CLOUD_VLLM

    def route_with_profile(
        self,
        task: Any,
        model_size_gb: float,
        profile: HardwareProfile,
        prefer_local: bool = True,
    ) -> ComputeTarget:
        """Route using a structured HardwareProfile snapshot."""
        return self.route(
            task=task,
            model_size_gb=model_size_gb,
            gpu_available=profile.gpu_available,
            vram_free_gb=profile.vram_free_gb,
            battery_pct=profile.battery_pct if not profile.is_plugged_in else 100.0,
            prefer_local=prefer_local,
        )
