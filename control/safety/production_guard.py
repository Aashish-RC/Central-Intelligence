"""Shared production safety guard for Central-Intelligence adapters.

Labels every adapter execution path as ``live`` or ``simulated`` using
environment configuration and enforces fail-closed behavior whenever
``ENVIRONMENT=production``.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

VALID_ADAPTER_MODES = ("live", "simulated")
_PROD_ALIASES = frozenset({"production", "prod", "live"})
_DEV_ALIASES = frozenset({
    "development",
    "dev",
    "test",
    "testing",
    "sandbox",
    "local",
})
_MOCK_SENTINEL_PREFIXES = ("mock", "test", "dummy", "fake", "placeholder")
_KNOWN_INSECURE_DEFAULTS = frozenset({
    "mock-secret-key",
    "coolify_mock_token",
    "mock_key",
    "sk-central-vlm-gateway",
    "gateway-secret",
    "devkey",
    "secret",
})


class ProductionSafetyError(RuntimeError):
    """Raised when a simulated adapter, mock credential, or fallback is used in production."""


def get_environment_name() -> str:
    """Resolve environment name from ``ENVIRONMENT`` or ``ENV``.

    Fails closed with ``ProductionSafetyError`` if conflicting modes are configured.
    """
    raw_env_var = os.getenv("ENVIRONMENT")
    raw_short_env = os.getenv("ENV")

    env_val = raw_env_var.strip().lower() if raw_env_var is not None else None
    short_val = raw_short_env.strip().lower() if raw_short_env is not None else None

    # Handle empty strings as unset
    if env_val == "":
        env_val = None
    if short_val == "":
        short_val = None

    if env_val is None and short_val is None:
        return "development"

    if env_val is not None and short_val is None:
        return env_val

    if short_val is not None and env_val is None:
        return short_val

    # Both are set and non-empty: check for contradictory production status
    assert env_val is not None and short_val is not None
    is_env_prod = env_val in _PROD_ALIASES
    is_short_prod = short_val in _PROD_ALIASES

    if is_env_prod != is_short_prod:
        raise ProductionSafetyError(
            f"Conflicting environment configuration: ENVIRONMENT='{raw_env_var}' and "
            f"ENV='{raw_short_env}'. Production detection cannot be ambiguously bypassed."
        )

    return env_val


def is_production() -> bool:
    """Return True if running in production mode via ``ENVIRONMENT`` or ``ENV``.

    Fails closed with ``ProductionSafetyError`` if configuration values conflict.
    """
    env_name = get_environment_name()
    return env_name in _PROD_ALIASES


def get_adapter_mode(adapter_name: str, default: str = "simulated") -> str:
    """Resolve adapter mode (``live`` or ``simulated``).

    Precedence: ``<NAME>_ADAPTER_MODE`` -> ``<NAME>_MODE`` -> ``ADAPTER_MODE`` -> ``default``.
    """
    norm = adapter_name.strip().upper().replace("-", "_")
    raw = (
        os.getenv(f"{norm}_ADAPTER_MODE")
        or os.getenv(f"{norm}_MODE")
        or os.getenv("ADAPTER_MODE")
        or default
    )
    mode = raw.strip().lower()
    if mode not in VALID_ADAPTER_MODES:
        msg = (
            f"Invalid adapter mode '{raw}' for {adapter_name}. "
            f"Expected one of {VALID_ADAPTER_MODES}."
        )
        if is_production():
            raise ProductionSafetyError(msg)
        raise ValueError(msg)
    return mode


def is_insecure_secret(value: Optional[str]) -> bool:
    """Return True if credential is empty or matches a known mock/placeholder secret."""
    if not value or not value.strip():
        return True
    lowered = value.strip().lower()
    if lowered in _KNOWN_INSECURE_DEFAULTS:
        return True
    return any(
        lowered.startswith(prefix)
        and ("mock" in lowered or "dummy" in lowered or "placeholder" in lowered)
        for prefix in _MOCK_SENTINEL_PREFIXES
    )


def require_live_adapter(
    adapter_name: str,
    *,
    require_credentials: Optional[Mapping[str, Optional[str]]] = None,
) -> str:
    """Call at adapter init or execution. Fails closed if simulated in production."""
    mode = get_adapter_mode(adapter_name, default="simulated")
    norm = adapter_name.strip().upper().replace("-", "_")

    if is_production():
        if mode != "live":
            raise ProductionSafetyError(
                f"{adapter_name} adapter is in '{mode}' mode. "
                f"Production requires '{norm}_MODE=live' (or '{norm}_ADAPTER_MODE=live')."
            )
        if require_credentials:
            for cred_name, cred_val in require_credentials.items():
                if is_insecure_secret(cred_val):
                    raise ProductionSafetyError(
                        f"{adapter_name} adapter requires a valid non-mock '{cred_name}' in production."
                    )

    return mode


def fail_closed_in_production(
    adapter_name: str,
    reason: str,
    cause: Optional[BaseException] = None,
) -> None:
    """Raise ``ProductionSafetyError`` when in production or explicit live mode."""
    mode = get_adapter_mode(adapter_name, default="simulated")
    if is_production() or mode == "live":
        err = ProductionSafetyError(
            f"{adapter_name} adapter cannot fall back to simulated mode: {reason}"
        )
        if cause is not None:
            raise err from cause
        raise err

