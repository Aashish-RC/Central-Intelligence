"""Email Ingestion Engine (L3 Feature 3.08).

Parses RFC-822 (.eml) and Outlook (.msg text/MIME fallback) messages, extracting
headers, body text, and attachment filenames/metadata, then indexes into L3 store.
"""

from __future__ import annotations

import email
import re
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage
from typing import Dict, List, Optional

from cognitive.knowledge.ingest._store import InMemoryKnowledgeIndex, KnowledgeChunk, KnowledgeHit


@dataclass
class EmailAttachmentMeta:
    """Extracted metadata for an email attachment."""

    filename: str
    content_type: str
    size_bytes: int


@dataclass
class ParsedEmail:
    """Structured representation of an ingested email."""

    message_id: str
    subject: str
    sender: str
    recipients: List[str]
    date: str
    body_text: str
    attachments: List[EmailAttachmentMeta] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)


class EmailIngestor:
    """Parses EML/MSG email files and indexes their content for semantic/keyword search."""

    def __init__(self, index: Optional[InMemoryKnowledgeIndex] = None) -> None:
        self.index = index or InMemoryKnowledgeIndex()

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def parse_eml(self, raw_bytes: bytes | str) -> ParsedEmail:
        """Parse raw RFC-822 bytes or string into headers, body, and attachments."""
        data = raw_bytes.encode("utf-8", errors="replace") if isinstance(raw_bytes, str) else raw_bytes
        msg: EmailMessage = email.message_from_bytes(data, policy=policy.default)

        plain_parts: List[str] = []
        html_parts: List[str] = []
        attachments: List[EmailAttachmentMeta] = []

        if msg.is_multipart():
            for part in msg.walk():
                disp = part.get_content_disposition()
                filename = part.get_filename()
                ctype = part.get_content_type()
                if disp == "attachment" or filename:
                    payload = part.get_payload(decode=True) or b""
                    attachments.append(
                        EmailAttachmentMeta(
                            filename=filename or "unnamed.bin",
                            content_type=ctype,
                            size_bytes=len(payload),
                        )
                    )
                elif ctype == "text/plain":
                    plain_parts.append(part.get_content())
                elif ctype == "text/html":
                    html_parts.append(self._strip_html(str(part.get_content())))
        else:
            ctype = msg.get_content_type()
            content = str(msg.get_content())
            if ctype == "text/html":
                html_parts.append(self._strip_html(content))
            else:
                plain_parts.append(content)

        body = "\n".join(p.strip() for p in plain_parts if p and p.strip())
        if not body and html_parts:
            body = "\n".join(html_parts)

        to_raw = str(msg.get("To", ""))
        recipients = [addr.strip() for addr in to_raw.split(",") if addr.strip()]

        return ParsedEmail(
            message_id=str(msg.get("Message-ID", "")).strip() or "unknown-msg",
            subject=str(msg.get("Subject", "")).strip(),
            sender=str(msg.get("From", "")).strip(),
            recipients=recipients,
            date=str(msg.get("Date", "")).strip(),
            body_text=body.strip(),
            attachments=attachments,
            headers={k: str(v) for k, v in msg.items()},
        )

    def ingest(self, source_id: str, raw_email: bytes | str) -> ParsedEmail:
        """Parse and index headers, body, and attachment names into knowledge index."""
        parsed = self.parse_eml(raw_email)
        self.index.delete_source(source_id)

        att_names = ", ".join(a.filename for a in parsed.attachments)
        searchable = (
            f"Subject: {parsed.subject}\n"
            f"From: {parsed.sender}\n"
            f"To: {', '.join(parsed.recipients)}\n"
            f"Body: {parsed.body_text}\n"
            + (f"Attachments: {att_names}" if att_names else "")
        ).strip()

        self.index.add(
            KnowledgeChunk(
                chunk_id=f"{source_id}:email:0",
                source_id=source_id,
                modality="email",
                text=searchable,
                metadata={
                    "message_id": parsed.message_id,
                    "subject": parsed.subject,
                    "sender": parsed.sender,
                    "attachments": [a.filename for a in parsed.attachments],
                },
            )
        )
        return parsed

    def search(self, query: str, top_k: int = 5) -> List[KnowledgeHit]:
        return self.index.search(query, top_k=top_k, modality="email")

