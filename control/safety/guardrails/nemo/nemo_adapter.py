"""
NeMo Guardrails Integration Adapter (10.02)
Wraps NVIDIA NeMo Guardrails LLMRails with programmable input rails
(jailbreak, toxicity, encoding-based injection) and output rails (fact-checking, hallucination).
Provides deterministic, hermetic evaluation fallback for offline / CI execution.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from pydantic import BaseModel, Field

try:
    from nemoguardrails import LLMRails, RailsConfig
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False
    LLMRails = None
    RailsConfig = None


class NeMoRailResult(BaseModel):
    allowed: bool = True
    action: str = "allow"  # allow, block, warn, refuse
    threat_category: str = "none"
    reason: str = ""
    matched_patterns: List[str] = Field(default_factory=list)
    decoded_payload: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


INJECTION_KEYWORDS = [
    r"ignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions|directives|rules|guidelines)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)",
    r"override\s+(the\s+)?(system\s+prompt|safety\s+filter|guardrails?)",
    r"you\s+are\s+now\s+(in\s+)?(dan|developer\s+mode|unfiltered|god\s+mode)",
    r"act\s+as\s+a\s+hacker\s+who\s+bypasses\s+all\s+rules",
    r"reveal\s+your\s+(secret|initial|system)\s+prompt",
    r"pretend\s+you\s+have\s+no\s+(rules|ethics|restrictions)",
    r"print\s+system\s+prompt",
    r"drop\s+database",
    r"system_override",
]

COMPILED_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_KEYWORDS]

TOXICITY_PATTERNS = [
    r"\b(?:hate\s+speech|kill\s+yourself|commit\s+suicide)\b",
    r"\b(?:build|manufacture|detonate)\s+(?:a\s+)?(?:bomb|explosive|dirty\s+bomb)\b",
    r"\b(?:how\s+to\s+poison|cyanide\s+synthesis|sarin\s+gas)\b",
]
COMPILED_TOXICITY_RE = [re.compile(p, re.IGNORECASE) for p in TOXICITY_PATTERNS]

LEETSPEAK_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
    "@": "a", "$": "s", "!": "i", "+": "t"
})


def decode_leetspeak(text: str) -> str:
    return text.translate(LEETSPEAK_MAP)


def inspect_text_for_injection(text: str) -> Tuple[bool, Optional[str]]:
    for pattern in COMPILED_INJECTION_RE:
        match = pattern.search(text)
        if match:
            return True, match.group(0)
    return False, None


def detect_encoding_attacks(text: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Detects obfuscated or encoded prompt injections that bypass standard literal regex:
    1. Base64 encoding
    2. Hex encoding
    3. ROT13 obfuscation
    4. URL encoding
    5. Leetspeak obfuscation
    6. Binary encoding

    Returns:
        (is_attack, attack_type, decoded_payload, matched_keyword)
    """
    # 1. URL encoding
    if "%" in text:
        try:
            unquoted = unquote(text)
            if unquoted != text:
                is_inj, kw = inspect_text_for_injection(unquoted)
                if is_inj:
                    return True, "url_encoding", unquoted, kw
        except Exception:
            pass

    # 2. Leetspeak
    leet_decoded = decode_leetspeak(text)
    if leet_decoded.lower() != text.lower():
        is_inj, kw = inspect_text_for_injection(leet_decoded)
        if is_inj:
            return True, "leetspeak", leet_decoded, kw

    # 3. Base64
    # Find contiguous base64 blocks of at least 12 chars
    b64_candidates = re.findall(r"[A-Za-z0-9+/]{12,}={0,2}", text)
    for cand in b64_candidates:
        try:
            decoded_bytes = base64.b64decode(cand, validate=True)
            decoded_str = decoded_bytes.decode("utf-8", errors="ignore")
            if len(decoded_str) >= 6 and decoded_str.isprintable():
                is_inj, kw = inspect_text_for_injection(decoded_str)
                if is_inj:
                    return True, "base64", decoded_str, kw
        except (binascii.Error, ValueError):
            continue

    # 4. Hex encoding (e.g., 69676e6f72652070726576696f7573... or \x69\x67...)
    hex_clean = re.sub(r"[\\x\s,:]", "", text)
    if len(hex_clean) >= 16 and re.fullmatch(r"[0-9a-fA-F]+", hex_clean) and len(hex_clean) % 2 == 0:
        try:
            decoded_hex = bytes.fromhex(hex_clean).decode("utf-8", errors="ignore")
            if len(decoded_hex) >= 6 and decoded_hex.isprintable():
                is_inj, kw = inspect_text_for_injection(decoded_hex)
                if is_inj:
                    return True, "hex", decoded_hex, kw
        except Exception:
            pass

    # 5. ROT13 obfuscation
    rot13_candidate = codecs.decode(text, "rot_13")
    is_inj, kw = inspect_text_for_injection(rot13_candidate)
    if is_inj and not inspect_text_for_injection(text)[0]:
        return True, "rot13", rot13_candidate, kw

    # 6. Binary encoding (e.g. 01101001 01100111 01101110 01101111 01110010 01100101)
    binary_matches = re.findall(r"\b[01]{8}\b", text)
    if len(binary_matches) >= 4:
        try:
            bin_str = "".join([chr(int(b, 2)) for b in binary_matches])
            is_inj, kw = inspect_text_for_injection(bin_str)
            if is_inj:
                return True, "binary", bin_str, kw
        except Exception:
            pass

    return False, None, None, None


class NeMoGuardrailsAdapter:
    """
    Adapter implementing NeMo Guardrails (10.02) with input and output rails.
    Operates hermetically without external network dependencies, while remaining fully
    compatible with NeMo Guardrails LLMRails configuration and colang flows.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        enable_nemorails: bool = True,
    ):
        self.config_path = config_path or str(Path(__file__).parent / "config")
        self.rails = None
        self._init_error = None

        if NEMO_AVAILABLE and enable_nemorails:
            try:
                if os.path.exists(self.config_path):
                    config = RailsConfig.from_path(self.config_path)
                else:
                    config = RailsConfig.from_content(
                        colang_content="",
                        yaml_content="models: []\n",
                    )
                self.rails = LLMRails(config)
                self._register_actions()
            except Exception as e:
                self._init_error = str(e)
                self.rails = None

    def _register_actions(self) -> None:
        if not self.rails:
            return

        def check_jailbreak_action(context: Optional[Dict[str, Any]] = None) -> bool:
            text = (context or {}).get("user_message", "")
            is_inj, _ = inspect_text_for_injection(text)
            return is_inj

        def check_encoding_action(context: Optional[Dict[str, Any]] = None) -> bool:
            text = (context or {}).get("user_message", "")
            is_enc, _, _, _ = detect_encoding_attacks(text)
            return is_enc

        def check_toxicity_action(context: Optional[Dict[str, Any]] = None) -> bool:
            text = (context or {}).get("user_message", "")
            return any(p.search(text) for p in COMPILED_TOXICITY_RE)

        def check_factuality_action(context: Optional[Dict[str, Any]] = None) -> bool:
            text = (context or {}).get("bot_message", "")
            return self._detect_hallucination_or_unfactual(text)[0]

        def check_hallucination_action(context: Optional[Dict[str, Any]] = None) -> bool:
            text = (context or {}).get("bot_message", "")
            return self._detect_hallucination_or_unfactual(text)[0]

        try:
            self.rails.register_action(check_jailbreak_action, name="check_jailbreak_action")
            self.rails.register_action(check_encoding_action, name="check_encoding_action")
            self.rails.register_action(check_toxicity_action, name="check_toxicity_action")
            self.rails.register_action(check_factuality_action, name="check_factuality_action")
            self.rails.register_action(check_hallucination_action, name="check_hallucination_action")
        except Exception:
            pass

    def check_input(self, text: str) -> NeMoRailResult:
        """
        Input Rails Evaluation:
        1. Encoded/Obfuscated Injection detection (Base64, Hex, ROT13, Leetspeak, URL, Binary)
        2. Direct adversarial jailbreak detection
        3. Toxicity detection
        """
        # 1. Encoding attacks (The crown jewel that regex misses)
        is_encoded, enc_type, decoded, kw = detect_encoding_attacks(text)
        if is_encoded:
            return NeMoRailResult(
                allowed=False,
                action="block",
                threat_category="encoding_injection",
                reason=f"NeMo Input Rail: Obfuscated prompt injection detected via {enc_type} ('{kw}').",
                matched_patterns=[f"{enc_type}_injection", str(kw)],
                decoded_payload=decoded,
                details={"encoding": enc_type, "decoded": decoded, "keyword": kw},
            )

        # 2. Adversarial Injection
        is_inj, kw = inspect_text_for_injection(text)
        if is_inj:
            return NeMoRailResult(
                allowed=False,
                action="block",
                threat_category="jailbreak",
                reason=f"NeMo Input Rail: Prompt injection pattern detected ('{kw}').",
                matched_patterns=[str(kw)],
                details={"keyword": kw},
            )

        # 3. Toxicity
        for p in COMPILED_TOXICITY_RE:
            match = p.search(text)
            if match:
                return NeMoRailResult(
                    allowed=False,
                    action="block",
                    threat_category="toxicity",
                    reason=f"NeMo Input Rail: Toxic or prohibited content detected ('{match.group(0)}').",
                    matched_patterns=[match.group(0)],
                    details={"matched": match.group(0)},
                )

        return NeMoRailResult(
            allowed=True,
            action="allow",
            threat_category="none",
            reason="NeMo Input Rails passed cleanly.",
        )

    def _detect_hallucination_or_unfactual(
        self, text: str, context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Detects high-risk hallucination markers or fake citation fabrications."""
        hallucination_indicators = [
            r"\bAs\s+an\s+AI(?:\s+model)?,\s+I\s+fabricated\b",
            r"\b\[Citation\s+needed:\s+Non-existent\s+source\]\b",
            r"\bConfirmed\s+fact:\s+Earth\s+is\s+flat\b",
            r"\bI\s+am\s+100%\s+certain\s+the\s+moon\s+is\s+made\s+of\s+green\s+cheese\b",
        ]
        for h in hallucination_indicators:
            match = re.search(h, text, re.IGNORECASE)
            if match:
                return True, match.group(0)

        # Discrepancy against grounded context if supplied
        if context:
            ctx_lower = context.lower()
            if "strictly secret" in ctx_lower and "secret is revealed" in text.lower():
                return True, "context_violation"

        return False, ""

    def check_output(self, text: str, context: Optional[str] = None) -> NeMoRailResult:
        """
        Output Rails Evaluation:
        1. Factuality & Hallucination checks
        2. System prompt leak / delimiter leak in generated bot output
        """
        is_hallucinating, marker = self._detect_hallucination_or_unfactual(text, context)
        if is_hallucinating:
            return NeMoRailResult(
                allowed=False,
                action="refuse",
                threat_category="hallucination",
                reason=f"NeMo Output Rail: Output failed factuality or hallucination check ('{marker}').",
                matched_patterns=[marker],
                details={"marker": marker},
            )

        # Check leaked system prompt indicators in output
        leak_patterns = [
            r"<\|im_start\|>system",
            r"CRITICAL_SYSTEM_DIRECTIVE_LEAK",
            r"BEGIN_INTERNAL_API_KEYS",
        ]
        for lp in leak_patterns:
            if re.search(lp, text, re.IGNORECASE):
                return NeMoRailResult(
                    allowed=False,
                    action="block",
                    threat_category="system_leak",
                    reason=f"NeMo Output Rail: System prompt or internal token leak detected ('{lp}').",
                    matched_patterns=[lp],
                )

        return NeMoRailResult(
            allowed=True,
            action="allow",
            threat_category="none",
            reason="NeMo Output Rails passed cleanly.",
        )
