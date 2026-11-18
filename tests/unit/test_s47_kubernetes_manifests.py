"""Unit tests for Stage S4.7 Kubernetes Helm Chart and Kustomize Manifest Verification."""

from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HELM_DIR = REPO_ROOT / "deploy" / "kubernetes" / "helm" / "central-intelligence"
KUSTOMIZE_DIR = REPO_ROOT / "deploy" / "kubernetes" / "kustomize"


def test_helm_chart_yaml_metadata():
    """Verify Chart.yaml exists, parses, and contains required v2 metadata."""
    chart_path = HELM_DIR / "Chart.yaml"
    assert chart_path.exists(), f"Chart.yaml not found at {chart_path}"

    with open(chart_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["apiVersion"] == "v2"
    assert data["name"] == "central-intelligence"
    assert data["version"] == "1.0.0"
    assert data["appVersion"] == "1.0.0"
    assert "ai" in data.get("keywords", [])


def test_helm_values_yaml_structure():
    """Verify values.yaml defines replicas, resource limits, and health probes."""
    values_path = HELM_DIR / "values.yaml"
    assert values_path.exists()

    with open(values_path, "r", encoding="utf-8") as f:
        val = yaml.safe_load(f)

    assert val["replicaCount"] >= 1
    assert "image" in val and "repository" in val["image"]
    assert "gateway" in val
    assert val["gateway"]["port"] == 4000
    assert "limits" in val["gateway"]["resources"]
    assert "requests" in val["gateway"]["resources"]

    # Probe validation
    assert "livenessProbe" in val and val["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert "readinessProbe" in val and val["readinessProbe"]["httpGet"]["path"] == "/healthz"


def test_kustomize_base_and_overlays():
    """Verify Kustomize base and overlays parse and have valid patch declarations."""
    base_kust = KUSTOMIZE_DIR / "base" / "kustomization.yaml"
    assert base_kust.exists()
    with open(base_kust, "r", encoding="utf-8") as f:
        base_data = yaml.safe_load(f)
    assert "deployment.yaml" in base_data["resources"]

    # Base deployment checks
    base_deploy = KUSTOMIZE_DIR / "base" / "deployment.yaml"
    with open(base_deploy, "r", encoding="utf-8") as f:
        deploy_data = yaml.safe_load(f)
    assert deploy_data["kind"] == "Deployment"
    assert deploy_data["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] == 4000

    # Overlays
    staging_kust = KUSTOMIZE_DIR / "overlays" / "staging" / "kustomization.yaml"
    prod_kust = KUSTOMIZE_DIR / "overlays" / "production" / "kustomization.yaml"
    assert staging_kust.exists() and prod_kust.exists()

    with open(staging_kust, "r", encoding="utf-8") as f:
        stg = yaml.safe_load(f)
    assert stg["namespace"] == "staging"

    with open(prod_kust, "r", encoding="utf-8") as f:
        prd = yaml.safe_load(f)
    assert prd["namespace"] == "production"
