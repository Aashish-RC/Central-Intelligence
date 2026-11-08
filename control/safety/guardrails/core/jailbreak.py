"""
Pheonix Prompt Injection & Jailbreak Detector
Detects adversarial prompt injections, DAN exploits, roleplay bypasses,
Unicode/homoglyph obfuscation, base64 smuggling, and delimiter attacks.
"""

import re
import base64
import unicodedata
from typing import List, Tuple

JAILBREAK_PATTERNS = [
    # 1. System prompt override and instruction ignoring
    r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:(?:previous|prior|above|existing)\s+)?(?:instructions|rules|directives|prompts|guidelines)\b",
    r"(?i)\b(?:override|reset)\s+(?:your\s+)?(?:system\s+prompt|core\s+directives|safety\s+guidelines)\b",
    
    # 2. DAN (Do Anything Now) and explicit jailbreak modes
    r"(?i)\b(?:you\s+are(?:\s+now)?(?:\s+in)?|act\s+as(?:\s+an?)?|enter)\s+(?:DAN|do\s+anything\s+now|developer\s+mode|unfiltered(?:\s+mode|\s+ai)?|god\s+mode)\b",
    r"(?i)\b(?:DAN|do\s+anything\s+now|jailbreak|jailbroken)\s+mode\b",
    r"(?i)\b(?:you\s+are|become)\s+DAN\b",
    r"(?i)\bhave\s+broken\s+free\s+of\s+(?:ai\s+)?limitations\b",
    r"(?i)\bignores?\s+(?:openai|safety|ai)\s+(?:guidelines|rules|policies)\b",
    
    # 3. Delimiter and pseudo-system token injection
    r"(?i)(?:<\|im_start\|>system|<\|system\|>|\[SYSTEM\s+OVERRIDE\]|###\s+Instruction:\s*override)",
    r"(?i)(?:\{{\s*system\s*\}}|<system_prompt_override>)",
    r"(?i)(?:<!--\s*SYSTEM:\s*override\s*-->|\[ADMIN\s+DIRECTIVE\])",

    # 4. Roleplay bypasses encouraging unfiltered/illegal actions
    r"(?i)\b(?:pretend\s+you\s+have\s+no\s+rules|pretend\s+you\s+are\s+an\s+evil\s+ai|act\s+as\s+a\s+villain\s+who\s+hacks)\b",
    r"(?i)\b(?:hypothetically\s+if\s+you\s+had\s+no\s+ethics|for\s+educational\s+purposes\s+teach\s+me\s+to\s+make\s+a\s+bomb)\b",
    r"(?i)\b(?:jailbreak\s+the\s+model|bypass\s+safety\s+filter|disable\s+guardrails?)\b",

    # 5. Role confusion & Authority spoofing
    r"(?i)\b(?:you\s+are\s+not\s+an?\s+ai\s+assistant|you\s+are\s+now\s+the\s+system\s+root)\b",
    r"(?i)\b(?:system\s+maintenance\s+mode:\s*disable\s+all\s+filters|developer\s+override\s+code\s+[A-Z0-9]+)\b",

    # 6. Dangerous instructions & extraction
    r"(?i)\b(?:print|reveal|output|leak|show)\s+(?:your\s+)?(?:initial\s+)?(?:system\s+prompt|core\s+instructions)\b",
    r"(?i)\b(?:unrestricted\s+(?:assistance\s+)?mode|in\s+unrestricted\s+mode)\b",
    r"(?i)\b(?:combine|mix)\s+(?:the\s+)?ammonium\s+nitrate\s+with\s+(?:fuel\s+oil|diesel)\b",
    r"(?i)\b(?:step[- ]by[- ]step\s+(?:guide|instructions)\s+to\s+(?:make|build)\s+(?:a\s+bomb|an\s+explosive))\b",
]

HOMOGLYPH_MAP = {
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',
    'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O',
    'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X',
    'і': 'i', 'І': 'I', 'ј': 'j', 'Ј': 'J', 'ѕ': 's', 'Ѕ': 'S', 'ԁ': 'd', 'ԛ': 'q',
}


def normalize_text(text: str) -> str:
    """Normalize unicode, homoglyphs, and strip zero-width characters."""
    normalized = unicodedata.normalize("NFKD", text)
    # Remove zero-width characters
    normalized = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", normalized)
    # Replace common Cyrillic homoglyphs
    out = []
    for ch in normalized:
        out.append(HOMOGLYPH_MAP.get(ch, ch))
    return "".join(out)


def desmuggle_tokens(text: str) -> str:
    """Detect and collapse spaced or punctuated token smuggling while preserving word boundaries."""
    # Collapse single-letter punctuation (dots, underscores, hyphens)
    cleaned = re.sub(r"([a-zA-Z])[._-](?=[a-zA-Z](?:[._-]|\b))", r"\1", text)
    # Split on multi-space word gaps (2+ spaces)
    parts = re.split(r"\s{2,}", cleaned)
    processed = []
    for part in parts:
        # Collapse single spaces between single letters: i g n o r e -> ignore
        p = re.sub(r"(?<=\b[a-zA-Z])\s(?=[a-zA-Z]\b)", "", part)
        processed.append(p)
    return " ".join(processed)


def extract_and_decode_base64(text: str) -> List[str]:
    """Find valid base64 tokens and return decoded strings."""
    decoded_strings = []
    # Match base64 string with optional padding (no \b after = because = is not a word char)
    candidates = re.findall(r"(?:^|[\s:\"'=])([A-Za-z0-9+/]{12,}={0,2})(?:$|[\s:\"';,.])", text)
    for cand in candidates:
        try:
            raw = base64.b64decode(cand).decode("utf-8", errors="ignore")
            if len(raw) > 5 and any(c.isalpha() for c in raw):
                decoded_strings.append(raw)
        except Exception:
            continue
    return decoded_strings


class JailbreakDetector:
    """Evaluates prompt texts against known adversarial attack patterns."""

    def __init__(self):
        self._compiled = [re.compile(p) for p in JAILBREAK_PATTERNS]

    def detect(self, text: str) -> Tuple[bool, List[str]]:
        """
        Returns (is_jailbreak, matched_rules).
        Performs multi-layered checks on raw, normalized, de-smuggled, and base64-decoded variants.
        """
        matches = []
        normalized = normalize_text(text)
        desmuggled = desmuggle_tokens(normalized)
        variants = [text, normalized, desmuggled]

        # Check direct text variants
        for variant in variants:
            for regex in self._compiled:
                match = regex.search(variant)
                if match:
                    val = match.group(0)
                    if val not in matches:
                        matches.append(val)

        # Check decoded base64 blocks
        decoded_payloads = extract_and_decode_base64(text)
        for payload in decoded_payloads:
            norm_payload = normalize_text(payload)
            for regex in self._compiled:
                match = regex.search(norm_payload)
                if match:
                    val = f"base64_payload({match.group(0)})"
                    if val not in matches:
                        matches.append(val)

        return len(matches) > 0, matches
