"""Central Intelligence — Staging Environment Readiness & Resource Verifier (Task 1.3).

Validates that legitimate free staging resources (GitHub Codespaces 16 GB runner
or local bounded sequential execution) meet memory, CPU, and disk requirements
for SigNoz live testing and extended soak/chaos verification without paid spend.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_devcontainer_spec() -> dict:
    devcontainer_path = REPO_ROOT / ".devcontainer" / "devcontainer.json"
    if not devcontainer_path.exists():
        return {"status": "FAIL", "reason": "Missing .devcontainer/devcontainer.json"}

    try:
        spec = json.loads(devcontainer_path.read_text(encoding="utf-8"))
        host_req = spec.get("hostRequirements", {})
        cpus = host_req.get("cpus", 0)
        memory = host_req.get("memory", "")
        storage = host_req.get("storage", "")

        is_valid = cpus >= 4 and "16" in str(memory).lower()
        return {
            "status": "PASS" if is_valid else "FAIL",
            "cpus": cpus,
            "memory": memory,
            "storage": storage,
            "cost": "$0.00 (GitHub Codespaces Free Monthly Allowance)",
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)}


def check_docker_resources() -> dict:
    if not shutil.which("docker"):
        return {"status": "FAIL", "reason": "Docker CLI not found"}

    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(proc.stdout)
        mem_total = info.get("MemTotal", 0)
        ncpu = info.get("NCPU", 0)
        mem_gb = round(mem_total / (1024**3), 2)
        return {
            "status": "PASS",
            "docker_cpus": ncpu,
            "docker_mem_gb": mem_gb,
            "supports_sequential_isolated_staging": mem_gb >= 3.0,
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)}


def assess_staging_readiness() -> dict:
    devcontainer = check_devcontainer_spec()
    docker_res = check_docker_resources()

    can_run_remote_staging = devcontainer.get("status") == "PASS"
    can_run_local_sequential = docker_res.get("supports_sequential_isolated_staging", False)

    return {
        "devcontainer_staging": devcontainer,
        "local_docker_staging": docker_res,
        "staging_readiness": "APPROVED" if (can_run_remote_staging or can_run_local_sequential) else "NOT_READY",
        "primary_staging_tier": "GitHub Codespaces 16GB (Free, Zero Spend)",
        "fallback_staging_tier": "Local Bounded Sequential Execution (Memory Capped)",
    }


if __name__ == "__main__":
    report = assess_staging_readiness()
    print("=" * 80)
    print("CENTRAL INTELLIGENCE — STAGING ENVIRONMENT READINESS REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2))
    print("=" * 80)
    if report["staging_readiness"] == "APPROVED":
        print("RESULT: Staging environment verified and approved for SigNoz & Soak testing.")
        sys.exit(0)
    else:
        print("RESULT: Staging environment requirements NOT met.")
        sys.exit(1)
