"""Provider Health Tracker (L16 Compute - Task 16.26).

Monitors real-time availability, latency, rate limits (HTTP 429), and errors
across upstream inference providers (OpenAI, Anthropic, Google, vLLM, Ollama).
Enforces circuit-breaker state transitions: Provider down -> unhealthy; recovery -> healthy.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    DOWN = "down"


@dataclass
class ProviderHealthReport:
    """Current health snapshot for an inference provider."""
    provider_id: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    total_failures: int = 0
    rate_limited_until: Optional[float] = None
    last_error_message: Optional[str] = None
    last_latency_ms: float = 0.0
    updated_at: float = field(default_factory=time.time)


class ProviderHealthTracker:
    """Tracks availability, error states, and health transitions across model providers."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        default_rate_limit_cooldown_s: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.default_rate_limit_cooldown_s = default_rate_limit_cooldown_s
        self._providers: Dict[str, ProviderHealthReport] = {}

    def _get_or_create(self, provider_id: str) -> ProviderHealthReport:
        if provider_id not in self._providers:
            self._providers[provider_id] = ProviderHealthReport(provider_id=provider_id)
        return self._providers[provider_id]

    def record_success(self, provider_id: str, latency_ms: float = 100.0) -> ProviderStatus:
        """Record successful provider response; handles recovery transitions."""
        report = self._get_or_create(provider_id)
        report.total_requests += 1
        report.consecutive_successes += 1
        report.consecutive_failures = 0
        report.last_latency_ms = latency_ms
        report.updated_at = time.time()

        # If provider was down or degraded, check recovery threshold
        if report.status in (ProviderStatus.DOWN, ProviderStatus.DEGRADED, ProviderStatus.RATE_LIMITED):
            if report.consecutive_successes >= self.recovery_threshold:
                report.status = ProviderStatus.HEALTHY
                report.rate_limited_until = None
                report.last_error_message = None
                logger.info("Provider '%s' has recovered to HEALTHY state.", provider_id)
            else:
                report.status = ProviderStatus.DEGRADED

        return report.status

    def record_failure(
        self,
        provider_id: str,
        error_message: str,
        status_code: Optional[int] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> ProviderStatus:
        """Record an error from provider; triggers circuit-breaking."""
        report = self._get_or_create(provider_id)
        report.total_requests += 1
        report.total_failures += 1
        report.consecutive_failures += 1
        report.consecutive_successes = 0
        report.last_error_message = error_message
        report.updated_at = time.time()

        # Check for rate limiting (HTTP 429)
        if status_code == 429:
            cooldown = retry_after_seconds or self.default_rate_limit_cooldown_s
            report.rate_limited_until = time.time() + cooldown
            report.status = ProviderStatus.RATE_LIMITED
            logger.warning("Provider '%s' is RATE_LIMITED for %.1f seconds", provider_id, cooldown)
            return report.status

        # If consecutive failures exceed threshold -> DOWN
        if report.consecutive_failures >= self.failure_threshold:
            report.status = ProviderStatus.DOWN
            logger.error(
                "Provider '%s' transitioned to DOWN after %d consecutive failures: %s",
                provider_id,
                report.consecutive_failures,
                error_message,
            )
        else:
            report.status = ProviderStatus.DEGRADED

        return report.status

    def is_available(self, provider_id: str) -> bool:
        """Check if provider is available to take new inference requests."""
        if provider_id not in self._providers:
            return True

        report = self._providers[provider_id]

        if report.status == ProviderStatus.DOWN:
            return False

        if report.status == ProviderStatus.RATE_LIMITED:
            if report.rate_limited_until and time.time() < report.rate_limited_until:
                return False
            # Cooldown passed, allow probe request
            report.status = ProviderStatus.DEGRADED
            report.rate_limited_until = None
            return True

        return True

    def get_status(self, provider_id: str) -> ProviderStatus:
        """Return current status of provider."""
        report = self._get_or_create(provider_id)
        # Check rate-limit expiration
        if report.status == ProviderStatus.RATE_LIMITED:
            if report.rate_limited_until and time.time() >= report.rate_limited_until:
                report.status = ProviderStatus.DEGRADED
                report.rate_limited_until = None
        return report.status

    def get_report(self, provider_id: str) -> ProviderHealthReport:
        """Get full health report object."""
        return self._get_or_create(provider_id)

