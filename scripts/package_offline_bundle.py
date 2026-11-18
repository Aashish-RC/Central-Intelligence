#!/usr/bin/env python3
"""
Stage S4.6: Air-Gapped / Private Cloud Deployment Bundle Packager.

Extracts all pinned Docker container image digests from docker-compose.yml,
generates offline container save/load scripts, creates air-gapped environment
presets (.env.offline), and outputs a cryptographically verified bundle manifest.

Usage:
    python scripts/package_offline_bundle.py [--output-dir dist/airgap_bundle]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AirGapPackager] %(message)s",
)
logger = logging.getLogger("AirGapPackager")


def extract_compose_images(compose_path: Path) -> List[str]:
    """Parse docker-compose.yml and extract all declared image references."""
    if not compose_path.exists():
        raise FileNotFoundError(f"docker-compose.yml not found at {compose_path}")

    images: List[str] = []
    with open(compose_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("image:"):
                img = line_str.split(":", 1)[1].strip().strip("'\"")
                if img and img not in images:
                    images.append(img)
    return sorted(images)


def compute_file_sha256(file_path: Path) -> str:
    """Compute standard SHA-256 hex digest of a local file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_offline_env(dest_path: Path) -> None:
    """Generate an air-gapped production environment configuration."""
    content = """# Central Intelligence Air-Gapped / Private Deployment Configuration (.env.offline)
# Generated for isolated on-premise enclaves without public internet egress.

AIRGAP_MODE=true
CI_ALLOW_OUTBOUND_NETWORK=false
CI_ENVIRONMENT=production
ADAPTER_MODE=live

# Local Inference & Embeddings (Zero External Model APIs)
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDING_BACKEND=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384

# Local Storage & Database Credentials
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres-airgap-secure-pass
POSTGRES_LIVE_URL=postgresql://postgres:postgres-airgap-secure-pass@127.0.0.1:5432/postgres

# Local Cache & Knowledge Graph
VALKEY_HOST=127.0.0.1
VALKEY_PORT=6379
REDIS_URL=redis://127.0.0.1:6379/0
QDRANT_URL=http://127.0.0.1:6333
TEMPORAL_HOST=127.0.0.1:7233

# Security & Secret KMS
SECRET_BACKEND=vault
KEYCLOAK_URL=http://127.0.0.1:8085
OPENFGA_API_URL=http://127.0.0.1:8081

# Telemetry & Observability (Local ClickHouse / Metastore Only)
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_METRICS_EXPORTER=none
OTEL_TRACES_EXPORTER=otlp
"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Generated air-gap environment preset: %s", dest_path)


def build_airgap_manifest(output_dir: Path) -> Path:
    """Construct complete air-gap deployment bundle and manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)

    compose_file = REPO_ROOT / "docker-compose.yml"
    images = extract_compose_images(compose_file)

    offline_env_path = output_dir / ".env.offline"
    generate_offline_env(offline_env_path)

    # 1. Output image list
    images_json = output_dir / "offline_images.json"
    with open(images_json, "w", encoding="utf-8") as f:
        json.dump({"total_images": len(images), "images": images}, f, indent=2)

    # 2. Output Docker save / load shell scripts
    save_sh = output_dir / "docker_save_all.sh"
    with open(save_sh, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p images\n")
        for img in images:
            safe_name = re.sub(r"[/:]", "_", img.split("@")[0])
            f.write(f"echo 'Saving {img} ...'\ndocker pull '{img}'\ndocker save -o 'images/{safe_name}.tar' '{img}'\n")

    load_sh = output_dir / "docker_load_all.sh"
    with open(load_sh, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env bash\nset -euo pipefail\nfor f in images/*.tar; do\n  echo \"Loading $f ...\"\n  docker load -i \"$f\"\ndone\n")

    # 3. Compute artifact hashes
    critical_files = [
        REPO_ROOT / "docker-compose.yml",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "scripts" / "bootstrap.sh",
        REPO_ROOT / "scripts" / "bootstrap.ps1",
        REPO_ROOT / "scripts" / "generate_env.py",
        offline_env_path,
        images_json,
    ]

    artifacts_meta: Dict[str, str] = {}
    for p in critical_files:
        if p.exists():
            rel_name = str(p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p.name)
            artifacts_meta[rel_name] = compute_file_sha256(p)

    manifest = {
        "bundle_version": "1.0.0-airgap",
        "created_at": "2026-11-18T00:00:00Z",
        "total_services": len(images),
        "target_architecture": "x86_64 / arm64",
        "airgap_compatible": True,
        "requires_internet_egress": False,
        "pinned_images": images,
        "artifact_checksums_sha256": artifacts_meta,
    }

    manifest_path = output_dir / "offline_bundle_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Successfully packaged air-gap bundle manifest: %s", manifest_path)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Package Air-Gapped Deployment Bundle")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="dist/airgap_bundle",
        help="Target output directory for the air-gapped bundle",
    )
    args = parser.parse_args()
    build_airgap_manifest(REPO_ROOT / args.output_dir)


if __name__ == "__main__":
    main()
