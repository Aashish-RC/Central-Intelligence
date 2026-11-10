"""Unit tests for GrowthBookAdapter (Task 17.3)."""

import pytest
from platform.release.flags.growthbook_adapter import (
    GrowthBookAdapter,
    FeatureFlag,
)


@pytest.fixture
def growthbook():
    adapter = GrowthBookAdapter()
    return adapter


def test_toggle_flag(growthbook: GrowthBookAdapter):
    """Acceptance test: Toggle flag on and off."""
    flag_key = "fast_model_routing"
    growthbook.register_flag(FeatureFlag(key=flag_key, enabled=True, rollout_percentage=100.0))

    assert growthbook.is_on(flag_key, "usr_1") is True
    assert growthbook.is_on(flag_key, "usr_2") is True

    # Toggle off
    growthbook.toggle_flag(flag_key, False)
    assert growthbook.is_on(flag_key, "usr_1") is False
    assert growthbook.is_on(flag_key, "usr_2") is False


def test_canary_rollout_5_percent(growthbook: GrowthBookAdapter):
    """Acceptance test: 5% canary rollout."""
    flag_key = "new_generative_ui_v2"
    growthbook.register_flag(
        FeatureFlag(
            key=flag_key,
            enabled=True,
            rollout_percentage=5.0,  # 5% canary
            value="v2_experience",
            fallback_value="v1_experience",
        )
    )

    # Test over 1,000 distinct simulated user IDs
    sample_size = 1000
    enabled_count = 0
    for i in range(sample_size):
        user_id = f"user_{i}"
        res = growthbook.evaluate(flag_key, user_id)
        if res.is_on:
            enabled_count += 1
            assert res.value == "v2_experience"
        else:
            assert res.value == "v1_experience"

    pct = (enabled_count / sample_size) * 100.0
    # Expected: close to 5% (between 3% and 7% for 1,000 samples)
    assert 3.0 <= pct <= 7.0, f"Expected ~5% rollout, but got {pct}% ({enabled_count}/{sample_size})"


def test_deterministic_user_evaluation(growthbook: GrowthBookAdapter):
    """Same user consistently evaluates to the exact same bucket every time."""
    flag_key = "experimental_cot_prompt"
    growthbook.register_flag(
        FeatureFlag(
            key=flag_key,
            enabled=True,
            rollout_percentage=50.0,
            variations=["prompt_A", "prompt_B"],
        )
    )

    res1 = growthbook.evaluate(flag_key, "user_fixed_42")
    res2 = growthbook.evaluate(flag_key, "user_fixed_42")

    assert res1.is_on == res2.is_on
    assert res1.value == res2.value
    assert res1.bucket_hash == res2.bucket_hash
