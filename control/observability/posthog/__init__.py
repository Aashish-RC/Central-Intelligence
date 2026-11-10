"""PostHog Product Analytics Package."""

from .posthog_adapter import AnalyticsEvent, FunnelStepResult, PostHogAdapter

__all__ = ["PostHogAdapter", "AnalyticsEvent", "FunnelStepResult"]
