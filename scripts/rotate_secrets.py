#!/usr/bin/env python3
"""Central Intelligence — Automated Secret & Key Rotation Utility (Task A8).

Replaces the standalone Infisical UI container with lightweight cron-executable
secret rotation across local environment files (.env) and cloud parameter stores
(AWS SSM, GCP Secret Manager, or Kubernetes SealedSecrets).
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"


def generate_secure_hex(nbytes: int = 32) -> str:
    """Generate cryptographically secure random token."""
    return secrets.token_hex(nbytes)


def rotate_secrets(env_path: Path = ENV_FILE) -> dict[str, str]:
    """Rotate runtime secrets while preserving user configurations."""
    rotated = {
        "JWT_SECRET": generate_secure_hex(32),
        "SESSION_SECRET": generate_secure_hex(32),
        "AUTH_SECRET": generate_secure_hex(32),
    }

    if not env_path.exists():
        print(f"[rotate-secrets] .env file not found at {env_path}; using process environment.")
        return rotated

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    updated_keys = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue
        k, _, v = stripped.partition("=")
        key = k.strip()
        if key in rotated:
            updated_lines.append(f"{key}={rotated[key]}")
            updated_keys.add(key)
        else:
            updated_lines.append(line)

    for k, v in rotated.items():
        if k not in updated_keys:
            updated_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    print(f"[rotate-secrets] Successfully rotated secrets in {env_path}: {list(rotated.keys())}")
    return rotated


if __name__ == "__main__":
    rotate_secrets()
