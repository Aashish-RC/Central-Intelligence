"""Unit and live tests for LibreTranslate and Gateway Chat fallback translation routing."""
import json
import os
import pytest
import httpx

from translation.core.engine import OfflineTranslationEngine
from translation.engines.libre_engine import LibreTranslateEngine


@pytest.fixture
def fake_libretranslate_transport():
    """Fake transport simulating responsive LibreTranslate service."""
    captured_requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path.endswith("/translate"):
            body = json.loads(request.content.decode("utf-8"))
            text = body.get("q", "")
            target = body.get("target", "en")
            return httpx.Response(
                200,
                json={"translatedText": f"[{target.upper()}] {text}"},
            )
        return httpx.Response(404, json={"error": "Not found"})

    transport = httpx.MockTransport(handle_request)
    transport.captured_requests = captured_requests
    return transport


@pytest.fixture
def fake_gateway_fallback_transport():
    """Fake transport where LibreTranslate is unavailable and Gateway chat serves as fallback."""
    captured_requests = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        # LibreTranslate endpoint fails / offline
        if request.url.path.endswith("/translate"):
            return httpx.Response(503, json={"error": "LibreTranslate service unavailable"})

        # Model Gateway chat fallback
        if request.url.path.endswith("/v1/chat/completions"):
            body = json.loads(request.content.decode("utf-8"))
            messages = body.get("messages", [])
            assert len(messages) == 2
            assert "translator" in messages[0]["content"].lower()
            user_text = messages[1]["content"]

            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"Gateway-translated: {user_text}",
                            }
                        }
                    ]
                },
            )

        return httpx.Response(404, json={"error": "Not found"})

    transport = httpx.MockTransport(handle_request)
    transport.captured_requests = captured_requests
    return transport


@pytest.mark.asyncio
async def test_translation_routes_to_libretranslate_with_fake_transport(fake_libretranslate_transport):
    """Verify LibreTranslateEngine dispatches to LIBRETRANSLATE_URL/translate."""
    client = httpx.AsyncClient(transport=fake_libretranslate_transport)
    engine = LibreTranslateEngine(
        endpoint_url="http://fake-libretranslate.internal:5000",
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    res = await engine.translate("Hello world", source_lang="en", target_lang="es")
    assert res == "[ES] Hello world"
    assert len(fake_libretranslate_transport.captured_requests) == 1
    req = fake_libretranslate_transport.captured_requests[0]
    assert req.url.path == "/translate"
    payload = json.loads(req.content.decode("utf-8"))
    assert payload["q"] == "Hello world"
    assert payload["source"] == "en"
    assert payload["target"] == "es"


@pytest.mark.asyncio
async def test_translation_falls_back_to_gateway_chat_with_fake_transport(fake_gateway_fallback_transport):
    """Verify fallback to gateway /v1/chat/completions when LibreTranslate is unreachable."""
    client = httpx.AsyncClient(transport=fake_gateway_fallback_transport)
    engine = LibreTranslateEngine(
        endpoint_url="http://fake-libretranslate.internal:5000",
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    res = await engine.translate("Good morning", source_lang="en", target_lang="fr")
    assert res == "Gateway-translated: Good morning"
    assert len(fake_gateway_fallback_transport.captured_requests) == 2

    first_req = fake_gateway_fallback_transport.captured_requests[0]
    assert first_req.url.path == "/translate"

    second_req = fake_gateway_fallback_transport.captured_requests[1]
    assert second_req.url.path == "/v1/chat/completions"
    payload = json.loads(second_req.content.decode("utf-8"))
    assert payload["model"] == "llama3.2:1b"


@pytest.mark.asyncio
async def test_translation_offline_lexicon_fallback_when_both_fail():
    """Verify fallback to deterministic MockOfflineTranslationEngine when both services fail."""
    def fail_all(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "All remote endpoints down"})

    fake_failing_transport = httpx.MockTransport(fail_all)
    client = httpx.AsyncClient(transport=fake_failing_transport)
    engine = LibreTranslateEngine(
        endpoint_url="http://fake-libretranslate.internal:5000",
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    # Mock engine has known mapping "bonjour" -> "Hello"
    res = await engine.translate("Bonjour", source_lang="fr", target_lang="en")
    assert "Hello" in res


@pytest.mark.asyncio
async def test_offline_translation_engine_integration_with_fake_transport(fake_libretranslate_transport):
    """Verify top-level OfflineTranslationEngine uses detection, caching, and fake client."""
    client = httpx.AsyncClient(transport=fake_libretranslate_transport)
    engine = OfflineTranslationEngine(
        endpoint_url="http://fake-libretranslate.internal:5000",
        gateway_url="http://fake-gateway.internal:4000",
        http_client=client,
    )

    # First translation populates cache
    res1 = await engine.translate_async("Hello world", target="es", source="en")
    assert res1 == "[ES] Hello world"
    assert len(fake_libretranslate_transport.captured_requests) == 1

    # Second identical translation hits cache
    res2 = await engine.translate_async("Hello world", target="es", source="en")
    assert res2 == "[ES] Hello world"
    assert len(fake_libretranslate_transport.captured_requests) == 1  # No additional HTTP call


@pytest.mark.live
@pytest.mark.asyncio
async def test_translation_live():
    """Live test against running LibreTranslate or Gateway chat service."""
    if os.getenv("PHEONIX_LIVE") != "1":
        pytest.skip("PHEONIX_LIVE is not enabled (set PHEONIX_LIVE=1)")

    libre_url = os.getenv("LIBRETRANSLATE_URL", "http://localhost:5000")
    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:4000")

    async with httpx.AsyncClient(timeout=2.0) as client:
        has_libre = False
        has_gateway = False
        try:
            r = await client.get(f"{libre_url}/languages")
            if r.status_code == 200:
                has_libre = True
        except Exception:
            pass

        try:
            r = await client.get(f"{gateway_url}/health")
            if r.status_code == 200:
                has_gateway = True
        except Exception:
            pass

        if not has_libre and not has_gateway:
            pytest.skip("Neither live LibreTranslate nor Gateway service is reachable")

    engine = LibreTranslateEngine(endpoint_url=libre_url, gateway_url=gateway_url)
    res = await engine.translate("Hello world", source_lang="en", target_lang="es")
    assert len(res) > 0
