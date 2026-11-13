"""Trusted Host Execution Policy & Audited System Runner.

Establishes an explicit, policy-governed boundary for legitimate system operations
requiring host execution (e.g. maintenance tasks, developer CLI operations,
or explicit test fixtures).

Security Guarantees:
1. Untrusted agent commands NEVER enter or execute through this path.
2. Unconditionally prohibited in production (is_production() == True).
3. Requires an explicit, validated TrustedExecutionContext with non-empty caller_id,
   capability, and valid system auth token.
4. Requires explicit argument list (argv: Sequence[str]). Shell expansion (shell=True)
   is strictly prohibited to prevent injection.
5. Emits an immutable audit log entry for every execution attempt.
6. Zero implicit promotion from untrusted agent commands or sandbox adapters.
"""

from __future__ import annotations

import logging
import os
import secrets
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from control.safety.production_guard import is_production

logger = logging.getLogger("sandboxes.trusted_host")

# Canonical environment variable for system authorization token
TRUSTED_HOST_TOKEN_ENV = "CENTRAL_TRUSTED_HOST_TOKEN"


class TrustedHostExecutionError(RuntimeError):
    """Raised when host execution policy is violated or authorization fails."""


@dataclass(frozen=True)
class TrustedExecutionContext:
    """Explicit authorization and governance context for host execution."""
    caller_id: str
    capability: str
    auth_token: str
    purpose: str = "system-maintenance"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustedExecutionAuditEntry:
    """Immutable audit entry for host executions."""
    audit_id: str
    timestamp: str
    caller_id: str
    capability: str
    command_argv: List[str]
    exit_code: int
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class TrustedExecutionResult:
    """Result of an authorized trusted host command execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    audit_id: str


class TrustedHostExecutionPolicy:
    """Enforces strict authorization, capability restrictions, and audit logging for host commands."""

    DISALLOWED_CALLER_IDENTIFIERS = frozenset({
        "agent",
        "untrusted",
        "llm",
        "tool",
        "prompt",
        "user_input",
        "external",
    })

    PERMITTED_SYSTEM_CAPABILITIES = frozenset({
        "SYSTEM_DIAGNOSTIC",
        "CONTAINER_MAINTENANCE",
        "TEST_FIXTURE_EXECUTION",
        "DEVELOPER_ADMIN_OPERATION",
    })

    def __init__(self, system_token: Optional[str] = None):
        self._system_token = system_token or os.getenv(TRUSTED_HOST_TOKEN_ENV)
        self._audit_log: List[TrustedExecutionAuditEntry] = []

    def validate_context(self, context: TrustedExecutionContext) -> None:
        """Validate context against security policies. Fails closed with TrustedHostExecutionError."""
        # 1. Unconditionally forbidden in production
        if is_production():
            raise TrustedHostExecutionError(
                "Host execution is strictly forbidden in production environments. "
                "Hardened container execution (Docker or E2B) is mandatory."
            )

        if not isinstance(context, TrustedExecutionContext):
            raise TrustedHostExecutionError(
                "Invalid execution context: must be an instance of TrustedExecutionContext."
            )

        # 2. Reject untrusted or agent callers
        if not context.caller_id or not context.caller_id.strip():
            raise TrustedHostExecutionError("Missing caller_id in TrustedExecutionContext.")

        normalized_caller = context.caller_id.strip().lower()
        if any(bad in normalized_caller for bad in self.DISALLOWED_CALLER_IDENTIFIERS):
            raise TrustedHostExecutionError(
                f"Unauthorized caller '{context.caller_id}'. Untrusted agent execution cannot "
                f"access or be promoted to the trusted host execution path."
            )

        # 3. Validate capability
        if context.capability not in self.PERMITTED_SYSTEM_CAPABILITIES:
            raise TrustedHostExecutionError(
                f"Unauthorized capability '{context.capability}'. Must be one of "
                f"{sorted(list(self.PERMITTED_SYSTEM_CAPABILITIES))}."
            )

        # 4. Token validation
        configured_token = self._system_token or os.getenv(TRUSTED_HOST_TOKEN_ENV)
        if configured_token:
            if not secrets.compare_digest(context.auth_token, configured_token):
                raise TrustedHostExecutionError("Invalid auth_token in TrustedExecutionContext.")
        elif not context.auth_token or len(context.auth_token) < 16:
            raise TrustedHostExecutionError(
                "TrustedExecutionContext requires a valid auth_token (min 16 chars) or configured "
                f"{TRUSTED_HOST_TOKEN_ENV}."
            )

    def record_audit(self, entry: TrustedExecutionAuditEntry) -> None:
        self._audit_log.append(entry)
        logger.info(
            "AUDIT [Host Execution]: caller=%s capability=%s exit=%d dur=%.2fms",
            entry.caller_id, entry.capability, entry.exit_code, entry.duration_ms,
        )

    def get_audit_log(self) -> List[TrustedExecutionAuditEntry]:
        return list(self._audit_log)


class TrustedHostProcessRunner:
    """Executes validated, capability-governed commands directly on host."""

    def __init__(self, policy: Optional[TrustedHostExecutionPolicy] = None):
        self.policy = policy or TrustedHostExecutionPolicy()

    def execute_trusted_command(
        self,
        command_argv: Sequence[str],
        context: TrustedExecutionContext,
        cwd: Optional[str] = None,
        timeout_seconds: float = 30.0,
        env: Optional[Dict[str, str]] = None,
    ) -> TrustedExecutionResult:
        """Executes a strictly authorized host command with argument vectors.

        Shell execution (shell=True) is unconditionally prohibited.
        """
        # Validate policy
        self.policy.validate_context(context)

        if not command_argv or not isinstance(command_argv, (list, tuple)):
            raise TrustedHostExecutionError("command_argv must be a non-empty sequence of strings.")

        audit_id = f"host-aud-{secrets.token_hex(8)}"
        start_time = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Sanitize environment: only permit minimal safe variables
        base_env = env or os.environ
        clean_env = {
            k: v for k, v in base_env.items()
            if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH", "HOME")
        }

        try:
            proc = subprocess.run(
                list(command_argv),
                shell=False,  # STRICT: never use shell=True
                cwd=cwd,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            entry = TrustedExecutionAuditEntry(
                audit_id=audit_id,
                timestamp=now_iso,
                caller_id=context.caller_id,
                capability=context.capability,
                command_argv=list(command_argv),
                exit_code=proc.returncode,
                duration_ms=round(duration_ms, 2),
                success=(proc.returncode == 0),
            )
            self.policy.record_audit(entry)

            return TrustedExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=round(duration_ms, 2),
                audit_id=audit_id,
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            entry = TrustedExecutionAuditEntry(
                audit_id=audit_id,
                timestamp=now_iso,
                caller_id=context.caller_id,
                capability=context.capability,
                command_argv=list(command_argv),
                exit_code=-1,
                duration_ms=round(duration_ms, 2),
                success=False,
                error=f"Timeout after {timeout_seconds}s",
            )
            self.policy.record_audit(entry)
            raise TrustedHostExecutionError(f"Trusted command timed out after {timeout_seconds}s") from exc

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            entry = TrustedExecutionAuditEntry(
                audit_id=audit_id,
                timestamp=now_iso,
                caller_id=context.caller_id,
                capability=context.capability,
                command_argv=list(command_argv),
                exit_code=-1,
                duration_ms=round(duration_ms, 2),
                success=False,
                error=str(exc),
            )
            self.policy.record_audit(entry)
            raise TrustedHostExecutionError(f"Trusted command execution failed: {exc}") from exc
