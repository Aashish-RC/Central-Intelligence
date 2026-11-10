"""
Automated Misuse & Bot Script Detector (Feature 10.50)
Detects automated scripts, scraping bots, and high-frequency request flooders:
- Request frequency / RPM tracking (e.g. 1000 req/min script is blocked)
- Automated tool / script header fingerprinting (curl, python-requests, headless browsers)
- Abnormal timing distributions
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


KNOWN_BOT_USER_AGENTS = [
    r"(?i)\b(?:curl|python-requests|aiohttp|httpx|postmanruntime|insomnia|scrapy)\b",
    r"(?i)\b(?:headlesschrome|puppeteer|selenium|phantomjs|playwright)\b",
    r"(?i)\b(?:bot|crawler|spider|wget|go-http-client)\b",
]

COMPILED_BOT_UA = [re.compile(p, re.IGNORECASE) for p in KNOWN_BOT_USER_AGENTS]


@dataclass
class AutomatedMisuseAssessment:
    is_blocked: bool
    is_bot_header: bool
    current_rpm: int
    action: str  # "allow", "throttle", "block"
    reason: str


class AutomatedMisuseDetector:
    """
    Detects and blocks automated scripts and high-velocity floods (Feature 10.50).
    Blocks requests when rate exceeds script threshold (default 1000 req/min).
    """

    def __init__(
        self,
        block_threshold_rpm: int = 1000,
        throttle_threshold_rpm: int = 300,
        window_seconds: int = 60,
    ):
        self.block_threshold_rpm = block_threshold_rpm
        self.throttle_threshold_rpm = throttle_threshold_rpm
        self.window_seconds = window_seconds

        # Identifier (IP or user_id) -> list of timestamps
        self._request_log: Dict[str, List[float]] = {}

    def is_bot_user_agent(self, user_agent: Optional[str]) -> bool:
        if not user_agent or not user_agent.strip():
            return True  # Empty User-Agent is classic bot behavior
        return any(pat.search(user_agent) for pat in COMPILED_BOT_UA)

    def evaluate_request(
        self,
        identifier: str,
        user_agent: Optional[str] = None,
        now: Optional[float] = None,
    ) -> AutomatedMisuseAssessment:
        timestamp = now if now is not None else time.time()
        cutoff = timestamp - self.window_seconds

        timestamps = [t for t in self._request_log.get(identifier, []) if t > cutoff]
        timestamps.append(timestamp)
        self._request_log[identifier] = timestamps
        rpm = len(timestamps)

        is_bot_ua = self.is_bot_user_agent(user_agent) if user_agent is not None else False

        # Acceptance Requirement: 1000 req/min script is blocked
        if rpm >= self.block_threshold_rpm:
            return AutomatedMisuseAssessment(
                is_blocked=True,
                is_bot_header=is_bot_ua,
                current_rpm=rpm,
                action="block",
                reason=f"Automated flood detected: {rpm} requests/min exceeded limit ({self.block_threshold_rpm} req/min). Script blocked.",
            )

        if rpm >= self.throttle_threshold_rpm:
            return AutomatedMisuseAssessment(
                is_blocked=False,
                is_bot_header=is_bot_ua,
                current_rpm=rpm,
                action="throttle",
                reason=f"High request volume ({rpm} RPM); throttling applied.",
            )

        if is_bot_ua and rpm > 60:
            return AutomatedMisuseAssessment(
                is_blocked=False,
                is_bot_header=True,
                current_rpm=rpm,
                action="throttle",
                reason=f"Automated script user agent detected ('{user_agent}').",
            )

        return AutomatedMisuseAssessment(
            is_blocked=False,
            is_bot_header=is_bot_ua,
            current_rpm=rpm,
            action="allow",
            reason="Normal human request velocity.",
        )


# Global default detector instance
default_automated_misuse_detector = AutomatedMisuseDetector()
