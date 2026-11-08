"""Unit tests for Step 24: Browser Takeover & CAPTCHA detection subsystem."""

from browser_automation.core.agent import BrowserUseAgent
from browser_automation.core.models import BrowserAction, BrowserActionType, BrowserObservation
from browser_automation.core.takeover import (
    CaptchaDetector,
    TakeoverManager,
    TakeoverStatus,
    TakeoverTrigger,
)
from browser_automation.runtime.session_runner import BrowserSessionRunner


def test_captcha_detector_signatures():
    # Cloudflare Turnstile detection
    assert CaptchaDetector.detect("<div id='cf-turnstile-wrapper'>Verify</div>") == "Cloudflare Turnstile"
    # Google reCAPTCHA detection
    assert CaptchaDetector.detect("<script src='https://www.google.com/recaptcha/api.js'></script>") == "reCAPTCHA"
    # hCaptcha detection
    assert CaptchaDetector.detect("<iframe src='https://assets.hcaptcha.com/check'></iframe>") == "hCaptcha"
    # Generic challenge
    assert CaptchaDetector.detect("Please complete the security check to continue.") == "Generic Verification"
    # Normal safe page
    assert CaptchaDetector.detect("<html><body>Welcome to Pheonix Documentation</body></html>") is None


def test_takeover_manager_lifecycle():
    manager = TakeoverManager()
    events = []
    manager.register_listener(lambda req: events.append((req.status, req.request_id)))

    # Request takeover
    req = manager.request_takeover(
        session_id="sess_123",
        trigger=TakeoverTrigger.CAPTCHA_DETECTED,
        reason="Cloudflare Turnstile detected",
        url="https://secure.example.com/login",
        challenge_type="Cloudflare Turnstile",
    )
    assert req.status == TakeoverStatus.REQUESTED
    assert manager.get_active_takeover("sess_123") is not None
    assert len(events) == 1

    # Start interactive takeover
    in_prog = manager.start_takeover(req.request_id, operator_id="admin_user")
    assert in_prog.status == TakeoverStatus.IN_PROGRESS
    assert len(events) == 2

    # Resolve takeover
    resolved = manager.resolve_takeover(req.request_id, user_notes="Captcha completed", operator_id="admin_user")
    assert resolved.status == TakeoverStatus.RESOLVED
    assert manager.get_active_takeover("sess_123") is None
    assert len(events) == 3


def test_browser_agent_pauses_on_captcha_and_resumes():
    manager = TakeoverManager()
    runner = BrowserSessionRunner()
    agent = BrowserUseAgent(session_runner=runner, takeover_manager=manager)

    # Manually inject a CAPTCHA DOM snippet into runner's active observation
    runner.current_url = "https://example.com/protected"
    runner.custom_dom_snippet = "<div class='cf-turnstile'>Please verify you are human</div>"

    action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        target_selector="#submit-btn",
    )

    # Execute step - should be paused for human takeover
    report = agent.step(action)
    assert report.success is False
    assert report.extracted_data.get("takeover_required") is True
    req_id = report.extracted_data.get("request_id")
    assert req_id is not None

    active_req = manager.get_active_takeover(runner.profile.session_id)
    assert active_req is not None
    assert active_req.request_id == req_id

    # Resolve takeover and resume
    resume_report = agent.resolve_takeover_and_resume(
        request_id=req_id,
        action=action,
        operator_id="operator_alice",
        user_notes="Solved turnstile puzzle",
    )
    assert resume_report.success is True
    assert manager.get_active_takeover(runner.profile.session_id) is None
