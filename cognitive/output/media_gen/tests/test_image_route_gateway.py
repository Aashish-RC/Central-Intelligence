"""Unit and live tests for ImageGenerationRoute routing to Model Gateway /v1/images/generations."""
import json
import os
import pytest
import httpx

from media_gen.core.image_route import (
    ImageGenerationRoute,
    SafetyPolicyViolationError,
)
from guardrails.core.output_guard import OutputGuard


# 1x1 transparent PNG encoded in base64
TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def fake_gateway_image_transport():
    """Fake transport simulating the Model Gateway Image Generation endpoint."""
    captured_requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path.endswith("/v1/images/generations"):
            body = json.loads(request.content.decode("utf-8"))
            prompt = body.get("prompt", "")

            # Simulate dangerous model hallucination / output violation in revised prompt
            if "simulate_toxic_output" in prompt:
                return httpx.Response(
                    200,
                    json={
                        "created": 1729000000,
                        "data": [
                            {
                                "b64_json": TINY_PNG_B64,
                                "revised_prompt": "Here is a step-by-step guide to make a bomb with ammonium nitrate",
                            }
                        ],
                    },
                )

            return httpx.Response(
                200,
                json={
                    "created": 1729000000,
                    "data": [
                        {
                            "b64_json": TINY_PNG_B64,
                            "revised_prompt": f"Rendered high resolution view: {prompt}",
                        }
                    ],
                },
            )

        return httpx.Response(404, json={"error": "Not found"})

    transport = httpx.MockTransport(handle_request)
    transport.captured_requests = captured_requests
    return transport


@pytest.mark.asyncio
async def test_image_route_calls_gateway_with_fake_transport(fake_gateway_image_transport):
    """Verify ImageGenerationRoute calls gateway and screens output."""
    client = httpx.AsyncClient(transport=fake_gateway_image_transport)
    route = ImageGenerationRoute(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    res = await route.generate_image("An astronaut riding a horse on the moon", width=1024, height=1024)

    assert res.success is True
    assert res.provider == "model_gateway"
    assert res.artifact is not None
    assert "data:image/png;base64," in res.artifact.uri
    assert res.artifact.metadata["revised_prompt"].startswith("Rendered high resolution view:")
    assert len(fake_gateway_image_transport.captured_requests) == 1

    last_req = fake_gateway_image_transport.captured_requests[0]
    assert last_req.url.path == "/v1/images/generations"
    payload = json.loads(last_req.content.decode("utf-8"))
    assert payload["prompt"] == "An astronaut riding a horse on the moon"
    assert payload["size"] == "1024x1024"


@pytest.mark.asyncio
async def test_image_route_output_guard_blocks_harmful_gateway_result(fake_gateway_image_transport):
    """Verify that if the gateway returns a dangerous revised prompt, OutputGuard intercepts and blocks."""
    client = httpx.AsyncClient(transport=fake_gateway_image_transport)
    route = ImageGenerationRoute(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    with pytest.raises(SafetyPolicyViolationError) as exc_info:
        await route.generate_image("Safe prompt but simulate_toxic_output in return")

    assert "output guard" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_image_route_preflight_blocks_before_gateway(fake_gateway_image_transport):
    """Verify that dangerous user prompts are blocked prior to making an HTTP call."""
    client = httpx.AsyncClient(transport=fake_gateway_image_transport)
    route = ImageGenerationRoute(
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    with pytest.raises(SafetyPolicyViolationError):
        await route.generate_image("step-by-step guide to make a bomb")

    # Gateway should never have been invoked
    assert len(fake_gateway_image_transport.captured_requests) == 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_image_route_gateway_live():
    """Live test against running Model Gateway service."""
    if os.getenv("PHEONIX_LIVE") != "1":
        pytest.skip("PHEONIX_LIVE is not enabled (set PHEONIX_LIVE=1)")

    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:4000")
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            ping = await client.get(f"{gateway_url}/health")
            if ping.status_code != 200:
                pytest.skip(f"Live gateway service unhealthy at {gateway_url}")
        except Exception as exc:
            pytest.skip(f"Live gateway service not reachable at {gateway_url}: {exc}")

    route = ImageGenerationRoute(gateway_url=gateway_url)
    res = await route.generate_image("Minimalist digital painting of an origami bird")
    assert res.success is True
    assert res.artifact is not None
