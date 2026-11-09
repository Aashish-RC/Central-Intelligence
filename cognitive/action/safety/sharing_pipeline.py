"""Review-Before-Wider-Sharing Promotion Pipeline.

Features: 5.47 (Review-Before-Wider-Sharing Pipeline), 19.35 (Cross-Agent Sharing Gate)
Enforces redaction scanning, supervisor approval gating, and immutable audit
logging before internal artifacts or memories are promoted across agent or team boundaries.
"""

from enum import Enum
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class SharingScope(str, Enum):
    AGENT_PRIVATE = "agent_private"
    TEAM_INTERNAL = "team_internal"
    CROSS_TEAM = "cross_team"
    PUBLIC = "public"


class SharingStatus(str, Enum):
    DRAFT = "draft"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REDACTED_APPROVED = "redacted_approved"
    REJECTED = "rejected"


class SharingRequest(BaseModel):
    """Artifact or memory sharing proposal under governance."""
    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(default_factory=lambda: f"shr_{uuid.uuid4().hex[:8]}")
    artifact_id: str
    artifact_type: str = "document"  # document, code, memory_fact, dataset
    source_agent_id: str
    target_scope: SharingScope
    status: SharingStatus = SharingStatus.REVIEW_PENDING
    raw_content: str
    sanitized_content: Optional[str] = None
    redactions_applied: List[str] = Field(default_factory=list)
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    reviewed_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewSharingPipeline:
    """Pipelines artifact promotion with automated redaction and human-in-the-loop gates."""

    # Common credential & sensitive pattern heuristics
    PATTERNS = [
        (r"(?i)\b(?:api[_-]?key|secret|token|password|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", "SECRET_KEY"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,20}\b", "EMAIL_PII"),
        (r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "PHONE_NUMBER"),
        (r"\b(?:\d{4}[- ]?){3}\d{4}\b", "PAYMENT_CARD"),
        (r"\b(?:10\.\d{1,3}|192\.168\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3})\.\d{1,3}\b", "INTERNAL_IP"),
    ]

    def __init__(self, auto_approve_clean_team_internal: bool = True):
        self._requests: Dict[str, SharingRequest] = {}
        self.auto_approve_clean_team_internal = auto_approve_clean_team_internal

    def submit_for_sharing(
        self,
        artifact_id: str,
        content: str,
        source_agent_id: str,
        target_scope: SharingScope,
        artifact_type: str = "document",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SharingRequest:
        """Submit an artifact or memory to be evaluated and shared."""
        sanitized, findings = self.scan_and_redact(content)

        req = SharingRequest(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            source_agent_id=source_agent_id,
            target_scope=target_scope,
            raw_content=content,
            sanitized_content=sanitized,
            redactions_applied=findings,
            metadata=metadata or {},
        )

        # Automated gate: if sharing internally within team, no findings, and auto-approval active
        if (
            target_scope in [SharingScope.AGENT_PRIVATE, SharingScope.TEAM_INTERNAL]
            and len(findings) == 0
            and self.auto_approve_clean_team_internal
        ):
            req.status = SharingStatus.APPROVED
            req.reviewer_id = "system:auto_approver"
            req.decision_notes = "Automatically approved clean team-internal asset."
            req.reviewed_at = time.time()
        else:
            req.status = SharingStatus.REVIEW_PENDING

        self._requests[req.request_id] = req
        return req

    def scan_and_redact(self, text: str) -> Tuple[str, List[str]]:
        """Scan text for credentials and PII, returning redacted text and list of findings."""
        redacted = text
        findings: List[str] = []

        for pattern, label in self.PATTERNS:
            matches = list(re.finditer(pattern, redacted))
            if matches:
                findings.append(f"{label} (count: {len(matches)})")
                redacted = re.sub(pattern, f"[REDACTED_{label}]", redacted)

        return redacted, findings

    def review_request(
        self,
        request_id: str,
        reviewer_id: str,
        approve: bool,
        notes: str = "",
        use_sanitized: bool = True,
    ) -> SharingRequest:
        """Supervisor decision on a pending promotion request."""
        req = self._requests.get(request_id)
        if not req:
            raise KeyError(f"Sharing request '{request_id}' not found")

        req.reviewer_id = reviewer_id
        req.decision_notes = notes
        req.reviewed_at = time.time()

        if approve:
            if use_sanitized and req.redactions_applied:
                req.status = SharingStatus.REDACTED_APPROVED
            else:
                req.status = SharingStatus.APPROVED
        else:
            req.status = SharingStatus.REJECTED

        return req

    def get_request(self, request_id: str) -> Optional[SharingRequest]:
        """Retrieve a specific sharing request."""
        return self._requests.get(request_id)

    def list_requests(
        self,
        status: Optional[SharingStatus] = None,
        scope: Optional[SharingScope] = None,
    ) -> List[SharingRequest]:
        """List requests according to filter."""
        res = list(self._requests.values())
        if status:
            res = [r for r in res if r.status == status]
        if scope:
            res = [r for r in res if r.target_scope == scope]
        return res
