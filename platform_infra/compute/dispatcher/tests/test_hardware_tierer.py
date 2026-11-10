"""Unit tests for HardwareTierDispatcher (Task 16.1)."""

import pytest
from platform_infra.compute.dispatcher.hardware_tierer import (
    ComputeTarget,
    HardwareProfile,
    HardwareTierDispatcher,
)


@pytest.fixture
def dispatcher():
    return HardwareTierDispatcher(min_battery_threshold=20.0, vram_headroom_ratio=1.5)


def test_7b_model_runs_locally_when_gpu_available(dispatcher: HardwareTierDispatcher):
    """Acceptance test: 7B model runs locally when GPU and VRAM are available and battery > 20%."""
    # 7B model weight ~4.5 GB -> 4.5 * 1.5 = 6.75 GB needed
    model_size_7b = 4.5
    gpu_available = True
    vram_free = 16.0  # 16 GB RTX 4080/4090
    battery = 85.0

    target = dispatcher.route(
        task="code_generation",
        model_size_gb=model_size_7b,
        gpu_available=gpu_available,
        vram_free_gb=vram_free,
        battery_pct=battery,
    )
    assert target == ComputeTarget.LOCAL_OLLAMA


def test_70b_model_offloaded_to_cloud(dispatcher: HardwareTierDispatcher):
    """Acceptance test: 70B model offloaded to cloud when VRAM is insufficient locally."""
    # 70B model weight ~40 GB -> needs 60 GB VRAM
    model_size_70b = 40.0
    gpu_available = True
    vram_free = 16.0
    battery = 90.0

    target = dispatcher.route(
        task="complex_reasoning",
        model_size_gb=model_size_70b,
        gpu_available=gpu_available,
        vram_free_gb=vram_free,
        battery_pct=battery,
    )
    assert target == ComputeTarget.CLOUD_VLLM


def test_low_battery_offloads_to_cloud(dispatcher: HardwareTierDispatcher):
    """When battery <= 20%, even smaller models are offloaded to cloud to save power."""
    model_size_7b = 4.5
    gpu_available = True
    vram_free = 16.0
    battery = 15.0  # Low battery!

    target = dispatcher.route(
        task="summarization",
        model_size_gb=model_size_7b,
        gpu_available=gpu_available,
        vram_free_gb=vram_free,
        battery_pct=battery,
    )
    assert target == ComputeTarget.CLOUD_VLLM


def test_no_gpu_offloads_to_cloud(dispatcher: HardwareTierDispatcher):
    """When machine has no discrete or capable GPU, offload to cloud."""
    model_size_7b = 4.5
    gpu_available = False
    vram_free = 0.0
    battery = 100.0

    target = dispatcher.route(
        task="chat",
        model_size_gb=model_size_7b,
        gpu_available=gpu_available,
        vram_free_gb=vram_free,
        battery_pct=battery,
    )
    assert target == ComputeTarget.CLOUD_VLLM


def test_route_with_hardware_profile(dispatcher: HardwareTierDispatcher):
    """Test routing with HardwareProfile object."""
    profile = HardwareProfile(
        gpu_available=True,
        vram_free_gb=24.0,
        battery_pct=75.0,
        is_plugged_in=False,
    )
    target = dispatcher.route_with_profile(
        task="embedding",
        model_size_gb=2.0,
        profile=profile,
    )
    assert target == ComputeTarget.LOCAL_OLLAMA

