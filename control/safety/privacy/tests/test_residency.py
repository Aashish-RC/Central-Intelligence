"""
Tests for Data Residency and Geo-Fencing Enforcer (10.32)
Verifies EU user geo-fencing, model endpoint resolution, and US SigNoz telemetry blocking.
"""

import pytest
from control.safety.privacy.residency_enforcer import (
    DataRegion,
    DataResidencyEnforcer,
    ResidencyViolationError,
    detect_endpoint_region,
)
from control.observability.log_routing.tier_router import (
    LogEntry,
    TieredLogRouter,
)
from control.observability.signoz import SigNozAdapter
from control.safety.pii import DataClass, FourTierPIIScrubber


@pytest.fixture
def enforcer():
    return DataResidencyEnforcer()


def test_detect_endpoint_region():
    assert detect_endpoint_region("https://bedrock-runtime.eu-central-1.amazonaws.com") == DataRegion.EU
    assert detect_endpoint_region("https://ci-eu-francecentral.openai.azure.com") == DataRegion.EU
    assert detect_endpoint_region("https://ci-us-east.openai.azure.com") == DataRegion.US
    assert detect_endpoint_region("https://bedrock-runtime.us-east-1.amazonaws.com") == DataRegion.US
    assert detect_endpoint_region("https://bedrock-runtime.ap-southeast-1.amazonaws.com") == DataRegion.APAC
    assert detect_endpoint_region("https://api.openai.com/v1/chat/completions") == DataRegion.GLOBAL


def test_eu_user_resolved_to_eu_model_endpoints(enforcer):
    user_id = "user_munich_1"
    enforcer.set_user_residency(user_id, region=DataRegion.EU)

    azure_ep = enforcer.resolve_regional_endpoint(user_id, service_name="azure_openai")
    assert "francecentral" in azure_ep or "eu" in azure_ep

    bedrock_ep = enforcer.resolve_regional_endpoint(user_id, service_name="bedrock")
    assert "eu-central-1" in bedrock_ep


def test_eu_user_data_never_sent_to_us_endpoint(enforcer):
    """Acceptance Test: EU user's data never sent to US-region endpoint."""
    user_id = "user_berlin_gdpr"
    enforcer.set_user_residency(user_id, region=DataRegion.EU)

    # Compliant EU transfer is allowed
    assert enforcer.is_dispatch_allowed(user_id, target_region=DataRegion.EU) is True

    # US transfer must be strictly prohibited
    assert enforcer.is_dispatch_allowed(user_id, target_region=DataRegion.US) is False

    with pytest.raises(ResidencyViolationError) as exc_info:
        enforcer.assert_compliant_dispatch(
            user_id=user_id,
            target_region=DataRegion.US,
            target_service="us_gpt4_endpoint",
        )

    assert "geo-fenced to 'eu'" in str(exc_info.value)
    assert exc_info.value.user_region == "eu"
    assert exc_info.value.target_region == "us"


def test_us_and_global_user_dispatches(enforcer):
    us_user = "user_chicago"
    enforcer.set_user_residency(us_user, region=DataRegion.US)
    assert enforcer.is_dispatch_allowed(us_user, target_region=DataRegion.US) is True

    global_user = "user_worldwide"
    assert enforcer.is_dispatch_allowed(global_user, target_region=DataRegion.US) is True
    assert enforcer.is_dispatch_allowed(global_user, target_region=DataRegion.EU) is True


def test_eu_user_signoz_telemetry_blocked_from_us_collector():
    """Acceptance Test: L14 does not log EU data in US-region SigNoz."""
    enforcer = DataResidencyEnforcer()
    eu_user = "user_paris_gdpr"
    enforcer.set_user_residency(eu_user, region=DataRegion.EU)

    # SigNoz configured in US region
    us_signoz = SigNozAdapter(endpoint_url="https://signoz-us.internal:4317")
    us_signoz.region = "us"

    router = TieredLogRouter(
        signoz=us_signoz,
        residency_enforcer=enforcer,
    )

    entry = LogEntry(
        content="Operation performance latency: 12ms",
        level="INFO",
        user_id=eu_user,
        tenant_id="tenant_eu_subsidiary",
    )

    scrubbed = router.route(entry, data_class=DataClass.TELEMETRY)

    # Check routed history
    history_entry = router.get_routed_history()[-1]
    assert history_entry["user_id"] == "hashed"
    # External dispatch to US SigNoz must be suppressed
    assert history_entry["dispatched_external"] is False
