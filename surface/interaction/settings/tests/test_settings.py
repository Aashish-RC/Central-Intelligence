"""Unit tests for SettingsCenter (Task 18.10)."""

import pytest
from surface.interaction.settings.settings_center import (
    SettingsCenter,
)
from surface.interaction.onboarding.first_run import OnboardingStep


@pytest.fixture
def settings():
    return SettingsCenter()


def test_unified_settings_center_and_rtl_localization(settings: SettingsCenter):
    """Acceptance test: User configures all settings in one place; RTL works; first-run wizard sets up provider key."""
    # 1. First-run wizard sets up provider key
    settings.set_provider_key("anthropic", "sk-ant-api-live-key-999")
    assert settings.get_provider_key("anthropic") == "sk-ant-api-live-key-999"
    assert settings.onboarding.state.has_api_key is True
    assert settings.onboarding.state.configured_provider == "anthropic"

    # Complete wizard steps
    settings.onboarding.next_step()
    settings.onboarding.next_step()
    settings.onboarding.next_step()
    settings.onboarding.next_step()
    assert settings.onboarding.state.is_completed is True

    # 2. Configure accessibility
    settings.accessibility.update_settings(
        high_contrast=True,
        screen_reader_enabled=True,
        closed_captions=True,
    )
    assert settings.accessibility.profile.high_contrast is True
    assert settings.accessibility.profile.screen_reader_enabled is True

    # 3. Configure localization to Arabic -> verify RTL works automatically
    locale_profile = settings.localization.set_locale("ar-SA")
    assert locale_profile.is_rtl is True
    assert locale_profile.language_code == "ar"
    assert locale_profile.currency == "SAR"
    assert settings.localization.translate("welcome") == "مرحبًا بك في الاستخبارات المركزية"

    # 4. Verify unified snapshot
    snapshot = settings.get_settings_snapshot()
    assert snapshot.accessibility.high_contrast is True
    assert snapshot.locale.is_rtl is True
    assert snapshot.onboarding.is_completed is True
    assert snapshot.api_keys_configured.get("anthropic") is True
