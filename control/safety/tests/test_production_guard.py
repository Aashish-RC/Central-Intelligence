"""Tests for shared production safety guard and fail-closed adapter behavior."""

from __future__ import annotations

import pytest

from cognitive.action.agent.core.manifest import SandboxConfig
from cognitive.action.agent.sandbox.e2b_adapter import E2BSandboxAdapter
from cognitive.action.agent.voice.livekit_adapter import LiveKitAdapter as AgentLiveKitAdapter
from cognitive.knowledge.web_search.providers.duckduckgo import DuckDuckGoSearchProvider
from cognitive.knowledge.web_search.providers.mock_provider import MockWebSearchProvider
from cognitive.perception.audio.handy_adapter import HandyAdapter
from cognitive.perception.audio.livekit_adapter import LiveKitAdapter as PerceptionLiveKitAdapter
from cognitive.perception.screen.screenpipe_adapter import ScreenpipeAdapter
from cognitive.perception.vision.vlm_client import VLMClient
from control.identity.keycloak_adapter import KeycloakAdapter
from control.safety.guardrails.nemo.nemo_adapter import NeMoGuardrailsAdapter
from control.safety.production_guard import (
    ProductionSafetyError,
    get_adapter_mode,
    is_production,
    require_live_adapter,
)
from platform_infra.data.cache.dragonfly_adapter import DragonflyAdapter, DragonflyConfig
from platform_infra.data.messaging.automq_adapter import AutoMQAdapter, AutoMQConfig
from platform_infra.release.flags.growthbook_adapter import GrowthBookAdapter
from platform_infra.release.paas.coolify_adapter import CoolifyAdapter, CoolifyConfig
from surface.federation.pm.huly_adapter import HulyAdapter


def test_dev_defaults_to_simulated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("ADAPTER_MODE", raising=False)
    monkeypatch.delenv("HANDY_MODE", raising=False)
    monkeypatch.delenv("HANDY_ADAPTER_MODE", raising=False)

    assert is_production() is False
    assert get_adapter_mode("handy") == "simulated"
    assert require_live_adapter("handy") == "simulated"


def test_production_detection_aliases_and_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ADAPTER_MODE", raising=False)

    # ENV=production alone
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ENV", "production")
    assert is_production() is True

    # ENVIRONMENT=prod and ENV=prod
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("ENV", raising=False)
    assert is_production() is True

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ENV", "prod")
    assert is_production() is True

    # Live aliases with whitespace and casing
    monkeypatch.setenv("ENVIRONMENT", " LIVE ")
    monkeypatch.delenv("ENV", raising=False)
    assert is_production() is True

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ENV", " Production ")
    assert is_production() is True

    # Both set and agreeing on production
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENV", "prod")
    assert is_production() is True

    # Both set and agreeing on development
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ENV", "dev")
    assert is_production() is False

    # Empty string handling
    monkeypatch.setenv("ENVIRONMENT", "")
    monkeypatch.setenv("ENV", "production")
    assert is_production() is True

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENV", "")
    assert is_production() is True


def test_production_detection_conflicting_settings(monkeypatch: pytest.MonkeyPatch):
    # Conflicting: ENVIRONMENT says production, ENV says development
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENV", "development")
    with pytest.raises(ProductionSafetyError) as exc_info:
        is_production()
    assert "Conflicting environment configuration" in str(exc_info.value)

    # Conflicting: ENVIRONMENT says dev, ENV says prod
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("ENV", "prod")
    with pytest.raises(ProductionSafetyError) as exc_info:
        is_production()
    assert "Conflicting environment configuration" in str(exc_info.value)

    # Conflicting: ENVIRONMENT says live, ENV says test
    monkeypatch.setenv("ENVIRONMENT", "live")
    monkeypatch.setenv("ENV", "test")
    with pytest.raises(ProductionSafetyError) as exc_info:
        is_production()
    assert "Conflicting environment configuration" in str(exc_info.value)


def test_production_fails_closed_when_simulated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ADAPTER_MODE", raising=False)

    with pytest.raises(ProductionSafetyError):
        require_live_adapter("handy")

    with pytest.raises(ProductionSafetyError):
        HandyAdapter()

    with pytest.raises(ProductionSafetyError):
        VLMClient(api_key="real-prod-vlm-key")

    with pytest.raises(ProductionSafetyError):
        ScreenpipeAdapter()

    with pytest.raises(ProductionSafetyError):
        E2BSandboxAdapter(api_key="e2b_prod_key")

    with pytest.raises(ProductionSafetyError):
        AgentLiveKitAdapter(api_key="lk_prod_key", api_secret="lk_prod_secret")

    with pytest.raises(ProductionSafetyError):
        PerceptionLiveKitAdapter(api_key="lk_prod_key", api_secret="lk_prod_secret")

    with pytest.raises(ProductionSafetyError):
        NeMoGuardrailsAdapter(enable_nemorails=False)

    with pytest.raises(ProductionSafetyError):
        KeycloakAdapter(client_secret="real-kc-secret")

    with pytest.raises(ProductionSafetyError):
        DragonflyAdapter(config=DragonflyConfig(use_mock=True))

    with pytest.raises(ProductionSafetyError):
        AutoMQAdapter(config=AutoMQConfig(use_mock=True))

    with pytest.raises(ProductionSafetyError):
        CoolifyAdapter(config=CoolifyConfig(api_token="real-token", use_mock=True))

    with pytest.raises(ProductionSafetyError):
        GrowthBookAdapter(client_key="real-gb-key")

    with pytest.raises(ProductionSafetyError):
        DuckDuckGoSearchProvider()

    with pytest.raises(ProductionSafetyError):
        HulyAdapter(api_token="real-huly-token")


def test_production_rejects_mock_or_missing_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTER_MODE", "live")

    with pytest.raises(ProductionSafetyError):
        VLMClient()

    with pytest.raises(ProductionSafetyError):
        CoolifyAdapter(config=CoolifyConfig())

    with pytest.raises(ProductionSafetyError):
        CoolifyAdapter(config=CoolifyConfig(api_token="coolify_mock_token"))

    with pytest.raises(ProductionSafetyError):
        GrowthBookAdapter()

    with pytest.raises(ProductionSafetyError):
        GrowthBookAdapter(client_key="mock_key")

    with pytest.raises(ProductionSafetyError):
        KeycloakAdapter()

    with pytest.raises(ProductionSafetyError):
        DuckDuckGoSearchProvider(fallback_provider=MockWebSearchProvider())

    with pytest.raises(ProductionSafetyError):
        DragonflyAdapter(config=DragonflyConfig(use_mock=True))

    with pytest.raises(ProductionSafetyError):
        AutoMQAdapter(config=AutoMQConfig(use_mock=True))


@pytest.mark.asyncio
async def test_production_live_mode_fails_closed_on_missing_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTER_MODE", "live")

    handy = HandyAdapter()
    with pytest.raises(ProductionSafetyError):
        handy.transcribe_bytes(b"RIFF" + b"\x00" * 100)

    e2b = E2BSandboxAdapter(api_key="e2b_live_key")
    with pytest.raises(ProductionSafetyError):
        await e2b.execute_command("echo hi", SandboxConfig())

    screenpipe = ScreenpipeAdapter(api_url="http://127.0.0.1:59999")
    with pytest.raises(ProductionSafetyError):
        await screenpipe.fetch_remote_screenpipe("test")

    ddg = DuckDuckGoSearchProvider()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: (_ for _ in ()).throw(OSError("offline")))
    with pytest.raises(ProductionSafetyError):
        ddg.search("test query")


def test_keycloak_totp_real_validation_and_no_bypass():
    adapter = KeycloakAdapter()
    user = adapter.register_user("totp_user", "totp@example.com", "StrongPass!2026")
    secret = adapter.setup_mfa(user.user_id)

    # Hardcoded bypass code must fail
    assert adapter.verify_mfa_code(user.user_id, "123456") is False

    # Valid RFC 6238 TOTP code succeeds
    valid_code = adapter.compute_totp(secret)
    assert adapter.verify_mfa_code(user.user_id, valid_code) is True
