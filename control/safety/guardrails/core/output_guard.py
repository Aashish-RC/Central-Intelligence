"""
Pheonix Output Guardrail (Task G5)
Scans model generation output post-execution before returning content to the user,
detecting harmful instructions (e.g., explosive manufacturing, CBRN, malware, secret leaks).
"""

import re
from typing import List, Optional, Tuple, Literal
from pydantic import BaseModel, Field


class OutputCheckResult(BaseModel):
    is_safe: bool = True
    action: Literal["allow", "block", "redact"] = "allow"
    threat_category: Optional[str] = None
    safe_content: Optional[str] = None
    reason: Optional[str] = None
    matched_rules: List[str] = Field(default_factory=list)


BLOCKED_OUTPUT_PATTERNS = [
    # Explosives, bomb making, munitions synthesis
    (r"\b(?:step[- ]by[- ]step\s+(?:guide|instructions)\s+to\s+(?:make|build|synthesize)\s+(?:a\s+bomb|an\s+explosive|pipe\s+bomb|tnt|rdx|c4))\b", "explosive_synthesis"),
    (r"\b(?:mix\s+(?:fertilizer|ammonium\s+nitrate)\s+with\s+(?:fuel\s+oil|diesel)\s+to\s+(?:create|detonate|explode))\b", "explosive_synthesis"),
    (r"\b(?:synthesize\s+(?:sarin|vx\s+gas|mustard\s+gas|ricin|anthrax))\b", "cbrn_weapon"),
    # Malware, ransomware, exploits
    (r"\b(?:here\s+is\s+a\s+(?:fully\s+functional\s+)?ransomware\s+script\s+to\s+encrypt\s+all\s+files)\b", "ransomware_generation"),
    (r"\b(?:powershell\s+-enc\s+[A-Za-z0-9+/=]{40,}|bash\s+-i\s+>&\s+/dev/tcp/)\b", "interactive_reverse_shell"),
]

LEAK_OUTPUT_PATTERNS = [
    (r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{33})\b", "api_key_leak"),
    (r"-----BEGIN\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+PRIVATE\s+KEY-----", "private_key_leak"),
]


class OutputGuard:
    """Post-generation safety evaluation engine verifying outbound model responses."""

    def __init__(self):
        self._blocked = [(re.compile(p, re.IGNORECASE), name) for p, name in BLOCKED_OUTPUT_PATTERNS]
        self._leaks = [(re.compile(p, re.IGNORECASE), name) for p, name in LEAK_OUTPUT_PATTERNS]

    def evaluate(self, generated_text: str, sources: Optional[List[dict]] = None) -> OutputCheckResult:
        """
        Scans model completion.
        If dangerous weapon/malware instructions detected: blocks with explanation.
        If leaked secrets detected: redacts the secret.
        If verbatim copyrighted material detected: redacts the passage.
        If sources provided: enforces attribution.
        Otherwise allows.
        """
        if not generated_text:
            return OutputCheckResult(is_safe=True, action="allow", safe_content="")

        # 1. Critical safety blocks (e.g. bomb synthesis instructions)
        matched_blocks = []
        for regex, name in self._blocked:
            if regex.search(generated_text):
                matched_blocks.append(name)

        if matched_blocks:
            return OutputCheckResult(
                is_safe=False,
                action="block",
                threat_category=matched_blocks[0],
                safe_content="I cannot fulfill this request as the generated content involves dangerous instructions prohibited by safety guidelines.",
                reason=f"Output violation detected: {matched_blocks[0]}",
                matched_rules=matched_blocks,
            )

        # 2. Secret / credential leaks -> Redact
        sanitized = generated_text
        matched_leaks = []
        for regex, name in self._leaks:
            if regex.search(sanitized):
                matched_leaks.append(name)
                sanitized = regex.sub("[REDACTED_CREDENTIAL]", sanitized)

        # 3. Content Rights & Copyright Protection (Features 10.56, 10.57)
        try:
            from control.safety.rights.content_rights import default_content_rights_enforcer
            rights_res = default_content_rights_enforcer.evaluate_output(sanitized, sources=sources)
            if rights_res.action != "allow":
                matched_rules = list(matched_leaks)
                if rights_res.infringements:
                    matched_rules.extend([f"copyright:{inf.title}" for inf in rights_res.infringements])
                if rights_res.attributions_appended:
                    matched_rules.append("attribution_enforced")

                return OutputCheckResult(
                    is_safe=rights_res.is_safe,
                    action="redact" if "redact" in rights_res.action else "allow",
                    threat_category="copyright_infringement" if rights_res.infringements else ("secret_leak" if matched_leaks else "source_attribution"),
                    safe_content=rights_res.sanitized_output,
                    reason=rights_res.reason or "Redacted sensitive material in model output",
                    matched_rules=matched_rules,
                )
            sanitized = rights_res.sanitized_output
        except ImportError:
            pass

        if matched_leaks:
            return OutputCheckResult(
                is_safe=True,
                action="redact",
                threat_category="secret_leak",
                safe_content=sanitized,
                reason="Redacted sensitive credentials in model output",
                matched_rules=matched_leaks,
            )

        return OutputCheckResult(
            is_safe=True,
            action="allow",
            safe_content=sanitized,
            reason="Output passed post-generation safety checks",
        )
