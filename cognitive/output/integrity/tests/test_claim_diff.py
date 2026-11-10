"""Unit tests for Surgical Claim Diff Patcher (Feature 6.37)."""

import pytest
from cognitive.output.integrity.claim_diff_patcher import (
    ClaimDiffPatcher,
    RefutedClaim,
)


def test_surgical_claim_diff_patcher_replaces_only_refuted_sentences():
    patcher = ClaimDiffPatcher()

    original = (
        "The project launch was initiated on Monday. "
        "The Apollo 11 mission landed on Mars in 1969. "
        "All telemetry data confirms normal orbital trajectory."
    )

    refuted = [
        RefutedClaim(
            id="claim-apollo-mars",
            text="Apollo 11 mission landed on Mars",
            refutation_reason="Apollo 11 landed on the Moon, not Mars.",
        )
    ]

    corrections = {
        "claim-apollo-mars": "The Apollo 11 mission landed on the Moon in 1969."
    }

    patched = patcher.patch(original, refuted, corrections)

    # First sentence untouched
    assert "The project launch was initiated on Monday." in patched
    # Second sentence surgically corrected
    assert "The Apollo 11 mission landed on the Moon in 1969." in patched
    assert "Mars" not in patched
    # Third sentence untouched
    assert "All telemetry data confirms normal orbital trajectory." in patched


def test_claim_diff_patcher_with_multiple_claims():
    patcher = ClaimDiffPatcher()

    original = (
        "Sentence one is accurate. "
        "Sentence two claims gravity does not exist. "
        "Sentence three claims water is dry. "
        "Sentence four remains untouched."
    )

    refuted = [
        RefutedClaim(id="c1", text="gravity does not exist"),
        RefutedClaim(id="c2", text="water is dry"),
    ]

    corrections = {
        "c1": "Sentence two affirms gravity is a fundamental interaction.",
        "c2": "Sentence three confirms liquid water exhibits surface tension.",
    }

    result = patcher.patch_with_details(original, refuted, corrections)

    assert result.replaced_count == 2
    assert result.unchanged_count == 2
    assert "Sentence one is accurate." in result.patched_text
    assert "Sentence four remains untouched." in result.patched_text
    assert len(result.patches) == 2


def test_claim_diff_patcher_no_refuted_claims():
    patcher = ClaimDiffPatcher()
    original = "System operations are 100% within acceptable safety margins."
    patched = patcher.patch(original, [], {})
    assert patched == original

