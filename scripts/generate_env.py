"""Central Intelligence — Cryptographic Environment (.env) Generator & Synchronizer.

Populates missing configuration values and replaces placeholder strings with
cryptographically secure keys suitable for local/staging container initialization.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
from pathlib import Path


def generate_rsa_key_b64() -> str:
    """Generate a 2048-bit RSA private key in PEM format, base64 encoded."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return base64.b64encode(pem).decode("ascii")
    except ImportError:
        # Fallback pseudo-PEM if cryptography package is missing
        dummy = b"-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n"
        return base64.b64encode(dummy).decode("ascii")


def sync_env_file(repo_root: Path | None = None) -> Path:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    env_path = repo_root / ".env"
    example_path = repo_root / ".env.example"

    if not example_path.exists():
        raise FileNotFoundError(f".env.example not found at {example_path}")

    # Read existing .env if present
    existing_vars: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing_vars[k.strip()] = v.strip()

    example_lines = example_path.read_text(encoding="utf-8").splitlines()
    output_lines: list[str] = []

    for line in example_lines:
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
            output_lines.append(line)
            continue

        key, val = trimmed.split("=", 1)
        key = key.strip()
        val = val.strip()

        # If existing value is set and not a placeholder, keep it
        if key in existing_vars and not existing_vars[key].startswith("replace-with-"):
            output_lines.append(f"{key}={existing_vars[key]}")
            continue

        # Otherwise generate a cryptographically valid token
        new_val = val
        if "LAGO_RSA_PRIVATE_KEY" in key:
            new_val = generate_rsa_key_b64()
        elif "CREDS_KEY" in key or "JWT_SECRET" in key or "SECRET_KEY_BASE" in key:
            new_val = secrets.token_hex(32)  # 64 hex characters
        elif "ENCRYPTION_KEY" in key or "CREDS_IV" in key or "AUTH_SECRET" in key:
            new_val = secrets.token_hex(16)  # 32 hex characters
        elif "PASSWORD" in key:
            new_val = f"ci_pass_{secrets.token_hex(12)}"
        elif "SECRET" in key or "MASTER_KEY" in key:
            new_val = secrets.token_hex(20)
        elif "LIVEKIT_KEYS" in key:
            new_val = f"livekit_key_{secrets.token_hex(8)}: livekit_sec_{secrets.token_hex(16)}"
        elif "REASONING_GATEWAY_API_KEY" in key:
            new_val = f"ci_gw_{secrets.token_hex(16)}"
        elif "LIBRECHAT_MONGO_USER" in key:
            new_val = "librechat"
        elif "LIBRECHAT_GATEWAY_URL" in key:
            new_val = "http://host.docker.internal:4000/v1"
        elif "GATEWAY_URL" in key:
            new_val = "http://localhost:4000"
        elif "POSTGRES_LIVE_URL" in key:
            db_pass = secrets.token_hex(12)
            new_val = f"postgresql://postgres:{db_pass}@localhost:5432/postgres"
        elif "POSTGRES_DB" in key:
            new_val = "postgres"
        elif "replace-with-" in val:
            new_val = secrets.token_hex(16)

        output_lines.append(f"{key}={new_val}")

    # Preserve any extra custom variables from existing .env not in .env.example
    example_keys = {
        l.split("=", 1)[0].strip()
        for l in example_lines
        if l.strip() and not l.strip().startswith("#") and "=" in l
    }
    extra_keys = [k for k in existing_vars if k not in example_keys]
    if extra_keys:
        output_lines.append("\n# Custom / Preserved Local Variables")
        for k in extra_keys:
            output_lines.append(f"{k}={existing_vars[k]}")

    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return env_path


if __name__ == "__main__":
    p = sync_env_file()
    print(f"Successfully synchronized {p}")
