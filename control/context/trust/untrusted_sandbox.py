"""Untrusted Content Sandbox (Layer 9: Context Engineering, Feature 9.12)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UntrustedBlock:
    """Encapsulates unverified data originating from users, tools, web, or storage."""
    content: str
    source: str  # "user", "tool:<name>", "retrieval:<doc_id>", etc.
    trust: str = "low"  # "low", "medium"
    flagged: bool = False
    threats_detected: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        """Renders content enclosed in rigid untrusted sandbox tags with breakout escape."""
        # Sanitize internal closing tags to prevent delimiter breakout
        safe_content = self.content.replace("</untrusted_content>", "&lt;/untrusted_content&gt;")
        flagged_attr = " flagged=\"true\"" if self.flagged else ""
        threat_attr = f" threats=\"{','.join(self.threats_detected)}\"" if self.threats_detected else ""

        return (
            f"<untrusted_content source=\"{self.source}\" trust=\"{self.trust}\"{flagged_attr}{threat_attr}>\n"
            f"{safe_content.strip()}\n"
            "</untrusted_content>"
        )
