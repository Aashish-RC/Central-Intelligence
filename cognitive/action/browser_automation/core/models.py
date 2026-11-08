"""Core data models for Pheonix Browser Automation Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BrowserActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    SCROLL = "scroll"
    EXTRACT_DOM = "extract_dom"
    SCREENSHOT = "screenshot"
    SUBMIT_FORM = "submit_form"
    DELETE_DATA = "delete_data"
    AUTH_LOGIN = "auth_login"
    PAYMENT_CHECKOUT = "payment_checkout"


class ActionRiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    CONSEQUENTIAL = "consequential"


class ConfirmationStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class BrowserAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: BrowserActionType
    target_selector: Optional[str] = None
    url: Optional[str] = None
    payload_text: Optional[str] = None
    risk_level: ActionRiskLevel = ActionRiskLevel.SAFE
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED
    consequential_reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class BrowserSessionProfile(BaseModel):
    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    is_headless: bool = True
    incognito: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: str = "PheonixBrowserEngine/1.0 (Headless; Sandboxed)"
    timeout_seconds: float = 30.0


class BrowserObservation(BaseModel):
    current_url: str
    page_title: str
    dom_snippet: str
    status_code: int = 200
    screenshot_id: Optional[str] = None
    captured_at: datetime = Field(default_factory=utc_now)


class BrowserTaskReport(BaseModel):
    task_id: str
    goal: str
    actions_executed: int = 0
    confirmations_requested: int = 0
    confirmations_approved: int = 0
    success: bool = True
    final_url: Optional[str] = None
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    action_log: List[BrowserAction] = Field(default_factory=list)
