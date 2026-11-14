"""
Untrusted Content Sandbox — Dual-Boundary Injection Defense (Layer 9).

Wraps untrusted content in XML boundary tags so the LLM parser treats it as data,
not instructions. Canonical tag form:

    <untrusted_content source="retrieval" trust="low" flagged="true" threats="prompt_injection">
      {escaped content with </untrusted_content> replaced by &lt;/untrusted_content&gt;}
    </untrusted_content>

Attributes:
  - source: origin of the content (retrieval, tool_output, user_input)
  - trust: trust level (low, medium, high)
  - flagged: True if the injection detector flagged the content
  - threats: comma-separated list of detected threat signatures
"""

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

    def __str__(self) -> str:
        return self.render()


# Alias for canonical usage
UntrustedSandbox = UntrustedBlock
