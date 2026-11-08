"""LibreTranslate REST client adapter with Model Gateway chat fallback."""
from __future__ import annotations

import os
from typing import Optional
import httpx
from translation.engines.base import BaseTranslationEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


class LibreTranslateEngine(BaseTranslationEngine):
    """Adapter for LibreTranslate with fallback to Model Gateway chat translation."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        gateway_url: Optional[str] = None,
        fallback: Optional[BaseTranslationEngine] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.endpoint_url = (endpoint_url or os.getenv("LIBRETRANSLATE_URL", "http://localhost:5000")).rstrip("/")
        self.gateway_url = (
            gateway_url
            or os.getenv("GATEWAY_URL")
            or os.getenv("MODEL_GATEWAY_URL", "http://localhost:4000")
        ).rstrip("/")
        self.fallback = fallback or MockOfflineTranslationEngine()
        self.http_client = http_client

    def name(self) -> str:
        return "libre_translate"

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if os.getenv("PHEONIX_LIVE") != "1" and self.http_client is None:
            return await self.fallback.translate(text, source_lang, target_lang)

        timeout = 10.0 if self.http_client is not None else 0.5
        client = self.http_client or httpx.AsyncClient(timeout=timeout)
        close_client = self.http_client is None

        # 1. Attempt translation via LibreTranslate
        try:
            libre_payload = {
                "q": text,
                "source": source_lang,
                "target": target_lang,
                "format": "text",
            }
            resp = await client.post(f"{self.endpoint_url}/translate", json=libre_payload)
            if resp.status_code == 200:
                translated = resp.json().get("translatedText")
                if translated:
                    return translated
        except Exception:
            pass

        # 2. If LibreTranslate unavailable, fall back to Gateway chat completion with translation prompt
        try:
            gateway_payload = {
                "model": "llama3.2:1b",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a translator. Translate the text directly from {source_lang} to {target_lang}. Output only the translation without explanations or conversational filler.",
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
                "max_tokens": 128,
            }
            resp = await client.post(f"{self.gateway_url}/v1/chat/completions", json=gateway_payload)
            if resp.status_code == 200:
                choices = resp.json().get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    if content:
                        return content
        except Exception:
            pass
        finally:
            if close_client:
                await client.aclose()

        # 3. Deterministic local fallback
        return await self.fallback.translate(text, source_lang, target_lang)
