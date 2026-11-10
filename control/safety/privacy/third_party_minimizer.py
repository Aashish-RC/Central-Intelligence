"""
Third-Party Personal Data Minimizer (Features 10.58, 10.59).

Features:
- 10.58: Personal data rules for NON-users. Identifies personal data belonging to non-users
  (names in uploaded documents, non-user emails, phone numbers, contact cards) and enforces strict
  proportionality and minimization requirements.
- 10.59: Multi-stage pipeline minimization: cleanses third-party personal data before:
  - L1 Input Gateway (inbound prompt scanning)
  - L2 Cognitive Memory (episodic & semantic storage)
  - L3 Knowledge & RAG (document ingestion & vector/text indexing)
  - L4 Model Dispatch (outbound LLM context payloads)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.safety.privacy.third_party")


@dataclass
class ThirdPartyEntity:
    """Represents a detected personal data item belonging to a non-user."""
    category: str  # "email", "phone", "ssn", "name", "credit_card"
    original_value: str
    replacement_value: str
    start: int
    end: int


@dataclass
class MinimizationResult:
    """Outcome of third-party data minimization."""
    original_text: str
    sanitized_text: str
    entities_redacted: List[ThirdPartyEntity] = field(default_factory=list)
    has_third_party_pii: bool = False
    total_redacted: int = 0
    stage: str = "general"


class ThirdPartyDataMinimizer:
    """
    Minimizes and sanitizes non-user personal data across ingestion, storage, and inference pipelines.
    """

    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    )
    PHONE_PATTERN = re.compile(
        r"(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?",
    )
    SSN_PATTERN = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b")

    # Document contact header patterns indicating third parties (horizontal whitespace only)
    THIRD_PARTY_NAME_PATTERNS = [
        re.compile(r"(?:Client|Customer|Patient|Vendor|Candidate|Third[- ]Party|Subject|Counterparty)\s*(?:Name)?:\s*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+)", re.I),
        re.compile(r"(?:Emergency Contact|Beneficiary|Witness|Reference):\s*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+)", re.I),
        re.compile(r"(?:Attn|Attention|CC):\s*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+)", re.I),
    ]

    def __init__(self, preserve_primary_user: bool = True):
        self.preserve_primary_user = preserve_primary_user

    def minimize(
        self,
        text: str,
        primary_user_email: Optional[str] = None,
        primary_user_name: Optional[str] = None,
        whitelist_emails: Optional[Set[str]] = None,
        stage: str = "general",
    ) -> MinimizationResult:
        """
        Scans text for personal data belonging to non-users and redacts them.
        If preserve_primary_user is True, primary user's credentials/name are preserved if configured.
        """
        if not text:
            return MinimizationResult(
                original_text="",
                sanitized_text="",
                has_third_party_pii=False,
                total_redacted=0,
                stage=stage,
            )

        known_whitelist: Set[str] = set()
        if self.preserve_primary_user and primary_user_email:
            known_whitelist.add(primary_user_email.strip().lower())
        if whitelist_emails:
            known_whitelist.update(e.strip().lower() for e in whitelist_emails)

        entities: List[ThirdPartyEntity] = []

        # 1. Detect and redact third-party emails
        for match in self.EMAIL_PATTERN.finditer(text):
            email_val = match.group(0)
            if email_val.lower() not in known_whitelist:
                entities.append(
                    ThirdPartyEntity(
                        category="email",
                        original_value=email_val,
                        replacement_value="[REDACTED_THIRD_PARTY_EMAIL]",
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # 2. Detect and redact phone numbers
        for match in self.PHONE_PATTERN.finditer(text):
            phone_val = match.group(0).strip()
            # Avoid matching short numbers or dates
            digits = re.sub(r"\D", "", phone_val)
            if len(digits) >= 10:
                entities.append(
                    ThirdPartyEntity(
                        category="phone",
                        original_value=phone_val,
                        replacement_value="[REDACTED_THIRD_PARTY_PHONE]",
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # 3. Detect and redact national IDs (SSN)
        for match in self.SSN_PATTERN.finditer(text):
            ssn_val = match.group(0)
            entities.append(
                ThirdPartyEntity(
                    category="ssn",
                    original_value=ssn_val,
                    replacement_value="[REDACTED_THIRD_PARTY_ID]",
                    start=match.start(),
                    end=match.end(),
                )
            )

        # 4. Detect and redact credit card numbers
        for match in self.CREDIT_CARD_PATTERN.finditer(text):
            cc_val = match.group(0)
            entities.append(
                ThirdPartyEntity(
                    category="credit_card",
                    original_value=cc_val,
                    replacement_value="[REDACTED_THIRD_PARTY_PAYMENT]",
                    start=match.start(),
                    end=match.end(),
                )
            )

        # 5. Detect and redact non-user names from structured doc headers
        for pattern in self.THIRD_PARTY_NAME_PATTERNS:
            for match in pattern.finditer(text):
                name_val = match.group(1).strip()
                # Skip if matches primary user's name
                if primary_user_name and name_val.lower() == primary_user_name.lower():
                    continue

                # Compute bounds of the extracted name capture group
                start_offset = match.start(1)
                end_offset = match.end(1)
                entities.append(
                    ThirdPartyEntity(
                        category="name",
                        original_value=name_val,
                        replacement_value="[REDACTED_THIRD_PARTY_NAME]",
                        start=start_offset,
                        end=end_offset,
                    )
                )

        # Deduplicate and sort entities by reverse start index to preserve substring positions
        deduped = sorted(
            {e.start: e for e in entities}.values(),
            key=lambda x: x.start,
            reverse=True,
        )

        sanitized = text
        for ent in deduped:
            sanitized = sanitized[: ent.start] + ent.replacement_value + sanitized[ent.end :]

        has_pii = len(deduped) > 0
        if has_pii:
            logger.info(
                "Stage '%s': Redacted %d third-party personal data entities.",
                stage,
                len(deduped),
            )

        return MinimizationResult(
            original_text=text,
            sanitized_text=sanitized,
            entities_redacted=list(reversed(deduped)),
            has_third_party_pii=has_pii,
            total_redacted=len(deduped),
            stage=stage,
        )

    # --- Feature 10.59 Multi-Stage Pipeline Helpers ---

    def scan_input(self, input_text: str, primary_user_email: Optional[str] = None) -> MinimizationResult:
        """L1 Input Gateway: Scans and sanitizes user input containing third-party personal data."""
        return self.minimize(input_text, primary_user_email=primary_user_email, stage="L1_input_gateway")

    def sanitize_for_storage(self, text_or_data: Any, primary_user_email: Optional[str] = None) -> MinimizationResult:
        """L2 Cognitive Memory: Ensures no raw third-party personal data is persisted."""
        text = str(text_or_data) if not isinstance(text_or_data, str) else text_or_data
        return self.minimize(text, primary_user_email=primary_user_email, stage="L2_memory_store")

    def sanitize_for_indexing(
        self,
        doc_content: str,
        primary_user_email: Optional[str] = None,
        whitelist_emails: Optional[Set[str]] = None,
    ) -> MinimizationResult:
        """
        L3 Knowledge & RAG Indexing: Redacts non-user personal data (third-party emails, names,
        phones) before indexing into Meilisearch or vector stores.
        """
        return self.minimize(
            doc_content,
            primary_user_email=primary_user_email,
            whitelist_emails=whitelist_emails,
            stage="L3_rag_indexing",
        )

    def sanitize_for_model(self, prompt_or_context: str, primary_user_email: Optional[str] = None) -> MinimizationResult:
        """L4 Model Dispatch: Minimizes third-party data in context payload before sending to LLM."""
        return self.minimize(prompt_or_context, primary_user_email=primary_user_email, stage="L4_model_dispatch")


# Global default singleton
default_third_party_minimizer = ThirdPartyDataMinimizer()
