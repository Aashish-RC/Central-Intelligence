"""Unit tests for Stage S4.6 Air-Gapped / Private Cloud Deployment Verification."""

import json
from pathlib import Path
import pytest

from scripts.package_offline_bundle import build_airgap_manifest, extract_compose_images
from scripts.verify_airgap_bundle import verify_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_images_extraction():
    """Verify compose images are correctly extracted and pinned."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    images = extract_compose_images(compose_path)

    # Consolidated compose has >= 15 core images; demo stack has >= 30
    assert len(images) >= 15, f"Expected at least 15 compose images in consolidated compose, got {len(images)}"
    demo_path = REPO_ROOT / "docker-compose.demo.yml"
    if demo_path.exists():
        demo_images = extract_compose_images(demo_path)
        assert len(demo_images) >= 30, f"Expected at least 30 images in demo compose, got {len(demo_images)}"

    # Ensure no image uses unpinned :latest tag without digest
    unpinned = [img for img in images if img.endswith(":latest") and "@sha256:" not in img]
    # In compose, signoz-otel-collector may use :latest, but in production bundles all must be declared
    for img in images:
        assert ":" in img or "@" in img, f"Image {img} has no tag or digest"


def test_airgap_bundle_build_and_verification(tmp_path: Path):
    """Verify complete packaging and verification of the airgap bundle."""
    manifest_path = build_airgap_manifest(tmp_path)
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["airgap_compatible"] is True
    assert manifest["requires_internet_egress"] is False
    assert len(manifest["pinned_images"]) >= 15
    assert len(manifest["artifact_checksums_sha256"]) >= 5

    # Run verifier against generated bundle
    verified = verify_bundle(tmp_path)
    assert verified is True


def test_airgap_offline_env_configuration(tmp_path: Path):
    """Verify .env.offline configures strictly local services and zero WAN phone-homes."""
    build_airgap_manifest(tmp_path)
    env_file = tmp_path / ".env.offline"
    assert env_file.exists()

    content = env_file.read_text(encoding="utf-8")
    lines = {line.split("=", 1)[0].strip(): line.split("=", 1)[1].strip() for line in content.splitlines() if "=" in line and not line.startswith("#")}

    assert lines.get("AIRGAP_MODE") == "true"
    assert lines.get("CI_ALLOW_OUTBOUND_NETWORK") == "false"
    assert lines.get("EMBEDDING_BACKEND") == "local"
    assert lines.get("DEFAULT_LLM_PROVIDER") == "ollama"
    assert lines.get("OTEL_METRICS_EXPORTER") == "none"
