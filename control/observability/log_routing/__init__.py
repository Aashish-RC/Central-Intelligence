"""4-Tier Structured Logging Subsystem."""

from .tier_router import LogEntry, TieredLogRouter

__all__ = ["TieredLogRouter", "LogEntry"]
