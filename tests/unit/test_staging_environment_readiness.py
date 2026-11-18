"""Unit tests for Task 1.3: Safe Staging Environment & Legitimate Free Resources.

Validates that .devcontainer/devcontainer.json defines 16 GB RAM and 4 CPUs,
and that staging verification logic confirms free legitimate staging pathways.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_staging_readiness import assess_staging_readiness, check_devcontainer_spec

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_devcontainer_16gb_staging_specification():
    """Verify .devcontainer/devcontainer.json requests 16 GB RAM and 4 CPUs."""
    devcontainer_file = REPO_ROOT / ".devcontainer" / "devcontainer.json"
    assert devcontainer_file.exists(), "Missing .devcontainer/devcontainer.json"

    data = json.loads(devcontainer_file.read_text(encoding="utf-8"))
    host_req = data.get("hostRequirements", {})

    assert host_req.get("cpus") == 4, "Staging runner requires 4 CPUs"
    assert host_req.get("memory") == "16gb", "Staging runner requires 16gb memory"
    assert host_req.get("storage") == "64gb", "Staging runner requires 64gb storage"


def test_staging_readiness_assessment():
    """Verify assessment confirms approved zero-cost staging pathways."""
    res = assess_staging_readiness()
    assert res["staging_readiness"] == "APPROVED"
    assert "16GB" in res["primary_staging_tier"]
    assert res["devcontainer_staging"]["status"] == "PASS"
    assert "$0.00" in res["devcontainer_staging"]["cost"]
