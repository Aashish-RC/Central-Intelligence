"""User Takeover and CAPTCHA Detection Subsystem for Browser Automation.

Allows headless/automated browser agents to detect bot-challenges, Cloudflare Turnstile,
reCAPTCHA, hCaptcha, and 2FA, pausing execution and handing control to a human operator.
"""

from datetime import datetime, timezone
from enum import Enum
import re
import threading
from typing import Any, Callable, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TakeoverStatus(str, Enum):
    IDLE = "idle"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


class TakeoverTrigger(str, Enum):
    CAPTCHA_DETECTED = "captcha_detected"
    BOT_CHALLENGE = "bot_challenge"
    INTERACTIVE_2FA = "interactive_2fa"
    MANUAL_REQUEST = "manual_request"


class TakeoverRequest(BaseModel):
    """Payload representing a human takeover event."""

    request_id: str = Field(default_factory=lambda: f"to_{uuid.uuid4().hex[:8]}")
    session_id: str
    trigger: TakeoverTrigger
    reason: str
    url: str
    challenge_type: Optional[str] = None
    dom_context: Optional[str] = None
    active_tab_id: Optional[str] = None
    tabs: List[Any] = Field(default_factory=list)
    status: TakeoverStatus = TakeoverStatus.REQUESTED
    requested_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    user_notes: Optional[str] = None


class CaptchaDetector:
    """Detects bot challenges, CAPTCHAs, and verification barriers from DOM/page content."""

    SIGNATURES = [
        ("Cloudflare Turnstile", [r"cf-turnstile", r"challenges\.cloudflare\.com", r"turnstile-wrapper"]),
        ("reCAPTCHA", [r"g-recaptcha", r"recaptcha/api", r"google\.com/recaptcha"]),
        ("hCaptcha", [r"hcaptcha\.com", r"h-captcha", r"assets\.hcaptcha\.com"]),
        ("Arkose / FunCaptcha", [r"arkoselabs\.com", r"funcaptcha"]),
        ("Generic Verification", [
            r"verify you are human",
            r"complete the security check to continue",
            r"press\s*(?:&|and)\s*hold",
            r"please slide to verify",
            r"bot detection",
            r"unusual traffic from your computer network",
        ]),
    ]

    @classmethod
    def detect(cls, content: str) -> Optional[str]:
        """Scans text or HTML snippet for known verification challenges.
        Returns the challenge type name if detected, otherwise None.
        """
        if not content:
            return None
        lower_content = content.lower()
        for challenge_name, patterns in cls.SIGNATURES:
            for pattern in patterns:
                if re.search(pattern, lower_content, re.IGNORECASE):
                    return challenge_name
        return None


class TakeoverManager:
    """Coordinates user takeover requests, callbacks, and lifecycle."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: Dict[str, TakeoverRequest] = {}
        self._active_session_takeovers: Dict[str, str] = {}  # session_id -> request_id
        self._listeners: List[Callable[[TakeoverRequest], None]] = []

    def register_listener(self, listener: Callable[[TakeoverRequest], None]) -> None:
        """Register a callback invoked when a takeover request is issued or updated."""
        with self._lock:
            self._listeners.append(listener)

    def _notify_listeners(self, request: TakeoverRequest) -> None:
        for listener in self._listeners:
            try:
                listener(request)
            except Exception:
                pass

    def request_takeover(
        self,
        session_id: str,
        trigger: TakeoverTrigger,
        reason: str,
        url: str,
        challenge_type: Optional[str] = None,
        dom_context: Optional[str] = None,
        screenshot_id: Optional[str] = None,
        active_tab_id: Optional[str] = None,
        tabs: Optional[List[Any]] = None,
    ) -> TakeoverRequest:
        """Issues a new takeover request and notifies subscribers."""
        with self._lock:
            req = TakeoverRequest(
                session_id=session_id,
                trigger=trigger,
                reason=reason,
                url=url,
                challenge_type=challenge_type,
                dom_context=dom_context,
                active_tab_id=active_tab_id,
                tabs=tabs or [],
                status=TakeoverStatus.REQUESTED,
            )
            self._requests[req.request_id] = req
            self._active_session_takeovers[session_id] = req.request_id

        self._notify_listeners(req)
        return req

    def switch_takeover_tab(self, request_id: str, tab_id: str) -> TakeoverRequest:
        """Switches the active focused tab during human takeover."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError(f"Takeover request '{request_id}' not found.")
            req.active_tab_id = tab_id
            for t in req.tabs:
                if isinstance(t, dict):
                    t["is_active"] = (t.get("tab_id") == tab_id)
                elif hasattr(t, "is_active"):
                    t.is_active = (getattr(t, "tab_id", "") == tab_id)
        self._notify_listeners(req)
        return req

    def get_active_takeover(self, session_id: str) -> Optional[TakeoverRequest]:
        """Returns the active unresolved takeover request for a session, if any."""
        with self._lock:
            req_id = self._active_session_takeovers.get(session_id)
            if not req_id:
                return None
            req = self._requests.get(req_id)
            if req and req.status in (TakeoverStatus.REQUESTED, TakeoverStatus.IN_PROGRESS):
                return req
            return None

    def start_takeover(self, request_id: str, operator_id: str = "human_user") -> TakeoverRequest:
        """Operator claims takeover and begins interactive session."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError(f"Takeover request '{request_id}' not found.")
            req.status = TakeoverStatus.IN_PROGRESS
            req.resolved_by = operator_id

        self._notify_listeners(req)
        return req

    def resolve_takeover(
        self,
        request_id: str,
        user_notes: Optional[str] = None,
        operator_id: str = "human_user",
    ) -> TakeoverRequest:
        """Operator completed challenge and returns control back to the agent."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError(f"Takeover request '{request_id}' not found.")
            req.status = TakeoverStatus.RESOLVED
            req.resolved_at = utc_now()
            req.resolved_by = operator_id
            req.user_notes = user_notes
            if req.session_id in self._active_session_takeovers:
                del self._active_session_takeovers[req.session_id]

        self._notify_listeners(req)
        return req

    def abort_takeover(
        self,
        request_id: str,
        reason: str = "User cancelled session",
        operator_id: str = "human_user",
    ) -> TakeoverRequest:
        """Operator cancelled or failed verification."""
        with self._lock:
            req = self._requests.get(request_id)
            if not req:
                raise ValueError(f"Takeover request '{request_id}' not found.")
            req.status = TakeoverStatus.ABORTED
            req.resolved_at = utc_now()
            req.resolved_by = operator_id
            req.user_notes = reason
            if req.session_id in self._active_session_takeovers:
                del self._active_session_takeovers[req.session_id]

        self._notify_listeners(req)
        return req
