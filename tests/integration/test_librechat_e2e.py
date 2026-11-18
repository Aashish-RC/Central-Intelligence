"""
Browser-level LibreChat End-to-End Test (Central Intelligence Task 2.2 / SC-05 follow-up).
Validates:
  Authenticated browser session -> LibreChat UI -> Custom Endpoint "Central Intelligence"
  -> Layer 4 Reasoning Gateway (/v1/chat/completions) -> Rendered assistant response in DOM.
"""

import os
import pytest
from playwright.async_api import async_playwright

pytestmark = [pytest.mark.integration, pytest.mark.requires_provisioned_services]

@pytest.mark.asyncio
async def test_librechat_browser_gateway_e2e():
    """Test full authenticated browser interaction through LibreChat to Central Intelligence Gateway."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()

        # 1. Login to LibreChat
        await page.goto("http://localhost:3080/login")
        await page.wait_for_selector("#email", timeout=15000)
        await page.fill("#email", "test99@example.com")
        await page.fill("#password", "TestPassword123!")
        await page.click("button[type='submit']")

        # 2. Verify redirect to /c/new
        await page.wait_for_url("**/c/new", timeout=15000)
        assert "/c/new" in page.url

        # 3. Select 'Central Intelligence' custom endpoint
        endpoint_menu = await page.wait_for_selector("[aria-label='LLM Endpoint Menu']", timeout=10000)
        await endpoint_menu.click()
        
        ci_option = await page.wait_for_selector("text='Central Intelligence'", timeout=10000)
        await ci_option.click()

        # 4. Input test prompt
        textarea = await page.wait_for_selector("#prompt-textarea", timeout=10000)
        test_prompt = "What is the capital of France? One word only."
        await textarea.fill(test_prompt)

        # 5. Submit message
        send_button = await page.wait_for_selector("#send-button", timeout=10000)
        await send_button.click()

        # 6. Verify assistant response bubble appears in DOM
        response_found = False
        for _ in range(20):
            await page.wait_for_timeout(1000)
            body_text = await page.inner_text("body")
            if "GPT-4o" in body_text and ("Output for task:" in body_text or "Paris" in body_text):
                response_found = True
                break

        assert response_found, f"Expected assistant response in DOM, got body:\n{body_text[-500:]}"

        # 7. Capture verifiable screenshot evidence
        evidence_path = os.path.abspath("tests/librechat_e2e_verified.png")
        await page.screenshot(path=evidence_path)
        assert os.path.exists(evidence_path), "Screenshot artifact was not created"

        await browser.close()
