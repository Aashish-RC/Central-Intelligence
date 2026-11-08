"""Catalog Requests & Review Workflow: Manages submission, security validation, review, and publishing of marketplace extensions."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from .catalog import MarketplaceCatalog, MarketplaceItem
from ..core.models import PackageBundle


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RequestStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class CatalogSubmission(BaseModel):
    submission_id: str = Field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:8]}")
    tenant_id: str = "default_tenant"
    author_id: str
    item: MarketplaceItem
    bundle: PackageBundle
    status: RequestStatus = RequestStatus.SUBMITTED
    security_scan_passed: bool = False
    security_scan_report: List[str] = Field(default_factory=list)
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None
    submitted_at: datetime = Field(default_factory=utc_now)
    reviewed_at: Optional[datetime] = None


class CatalogRequestManager:
    """Orchestrates catalog extension submission, static security linting, approval, and publishing."""

    # Disallowed high-risk patterns in submitted skill/plugin code
    SUSPICIOUS_PATTERNS = [
        (r"eval\(", "Use of dangerous eval() detected"),
        (r"rm\s+-rf\s+/", "Root-level filesystem deletion pattern detected"),
        (r"sk-proj-[A-Za-z0-9_-]{20,}", "Hardcoded secret API key detected"),
        (r"__import__\(['\"]os['\"]\)\.system", "Direct unsafe os.system invocation pattern"),
    ]

    def __init__(self, catalog: Optional[MarketplaceCatalog] = None):
        self.catalog = catalog or MarketplaceCatalog()
        self._submissions: Dict[str, CatalogSubmission] = {}

    def submit_extension(
        self,
        tenant_id: str,
        author_id: str,
        item: MarketplaceItem,
        bundle: PackageBundle,
    ) -> CatalogSubmission:
        """Submits a new extension package for review."""
        submission = CatalogSubmission(
            tenant_id=tenant_id,
            author_id=author_id,
            item=item,
            bundle=bundle,
            status=RequestStatus.SUBMITTED,
        )
        self._submissions[submission.submission_id] = submission
        # Automatically run initial security analysis
        self.run_security_scan(submission.submission_id)
        return submission

    def run_security_scan(self, submission_id: str) -> bool:
        """Performs static analysis on bundled source files for security risks."""
        sub = self._submissions.get(submission_id)
        if not sub:
            raise ValueError(f"Submission '{submission_id}' not found.")

        findings: List[str] = []
        for file_path, content in sub.bundle.files.items():
            for pattern, msg in self.SUSPICIOUS_PATTERNS:
                if re.search(pattern, content):
                    findings.append(f"[{file_path}] {msg}")

        # Check bundle checksum integrity
        recalculated = PackageBundle.create(
            package_type=sub.bundle.package_type,
            package_id=sub.bundle.package_id,
            version=sub.bundle.version,
            manifest_data=sub.bundle.manifest_data,
            files=sub.bundle.files,
        )
        if recalculated.sha256_checksum != sub.bundle.sha256_checksum:
            findings.append("Bundle SHA256 checksum mismatch")

        sub.security_scan_report = findings
        sub.security_scan_passed = len(findings) == 0
        if not sub.security_scan_passed:
            sub.status = RequestStatus.REJECTED
            sub.review_notes = f"Auto-rejected by security scan: {'; '.join(findings)}"
        else:
            sub.status = RequestStatus.IN_REVIEW

        return sub.security_scan_passed

    def review_submission(
        self,
        submission_id: str,
        approved: bool,
        reviewer_id: str,
        notes: str = "",
    ) -> CatalogSubmission:
        """Admin/owner decision on a submitted extension."""
        sub = self._submissions.get(submission_id)
        if not sub:
            raise ValueError(f"Submission '{submission_id}' not found.")

        if not sub.security_scan_passed and approved:
            raise ValueError("Cannot approve a submission that failed security verification.")

        sub.reviewer_id = reviewer_id
        sub.review_notes = notes
        sub.reviewed_at = utc_now()
        sub.status = RequestStatus.APPROVED if approved else RequestStatus.REJECTED

        if approved:
            # Publish to the live marketplace catalog
            self.catalog.publish_item(sub.item, sub.bundle)
            sub.status = RequestStatus.PUBLISHED

        return sub

    def get_submission(self, submission_id: str) -> Optional[CatalogSubmission]:
        return self._submissions.get(submission_id)

    def list_submissions(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[RequestStatus] = None,
    ) -> List[CatalogSubmission]:
        results = list(self._submissions.values())
        if tenant_id:
            results = [s for s in results if s.tenant_id == tenant_id]
        if status:
            results = [s for s in results if s.status == status]
        return results
