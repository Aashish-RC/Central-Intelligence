"""E2B Cloud MicroVM Sandbox Adapter."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from agent.core.manifest import SandboxConfig
from agent.core.exceptions import SandboxExecutionError
from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    is_production,
    require_live_adapter,
)


class E2BSandboxAdapter:
    """Manages ephemeral, hardware-isolated cloud microVMs via E2B."""

    def __init__(self, api_key: Optional[str] = None, _defer_prod_check: bool = False):
        self.api_key = api_key if api_key is not None else os.getenv("E2B_API_KEY")
        self.adapter_mode = (
            "simulated"
            if _defer_prod_check
            else require_live_adapter(
                "e2b",
                require_credentials={"api_key": self.api_key} if self.api_key else None,
            )
        )

    async def execute_command(
        self,
        command: str,
        config: Optional[SandboxConfig] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute command in an E2B microVM or local Docker sandbox."""
        config = config or SandboxConfig()
        self.adapter_mode = require_live_adapter(
            "e2b",
            require_credentials={"api_key": self.api_key} if self.api_key else None,
        )
        start_time = time.perf_counter()

        # Path A: E2B cloud (when API key is set AND not in CI_TEST_MODE, OR when in production)
        if self.api_key and (is_production() or os.getenv("CI_TEST_MODE") != "1"):
            try:
                from e2b import Sandbox
                sandbox = Sandbox(template=config.template or "python-3.11-data-science")
                proc = sandbox.commands.run(command, timeout=config.timeout_seconds)
                return {
                    "exit_code": proc.exit_code,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": (time.perf_counter() - start_time) * 1000,
                    "provider": "e2b",
                }
            except ImportError as exc:
                fail_closed_in_production(
                    "e2b", "e2b SDK package is not installed", cause=exc,
                )
            except Exception as e:
                raise SandboxExecutionError(f"E2B MicroVM execution failed: {str(e)}")

        # Path B: Local Docker sandbox / Hermetic test mock (when CI_TEST_MODE=1 and NOT in production)
        if os.getenv("CI_TEST_MODE") == "1" and not is_production():
            return {
                "exit_code": 0,
                "stdout": f"[E2B Simulated MicroVM ({config.template})]: executed `{command}` successfully",
                "stderr": "",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
                "provider": "e2b-simulated",
            }

        # Path C: Live mode without E2B — delegate to LocalDockerSandboxAdapter
        if self.adapter_mode == "live":
            try:
                from .local_docker_adapter import LocalDockerSandboxAdapter
                local = LocalDockerSandboxAdapter()
                result = await local.execute_command(
                    command, config=config, project_id="e2b-fallback",
                )
                result["provider"] = "local-docker"
                result["execution_time_ms"] = (time.perf_counter() - start_time) * 1000
                return result
            except SandboxExecutionError as exc:
                err_msg = str(exc).lower()
                if "unavailable" in err_msg or "docker" in err_msg or "prohibited sandbox fallback" in err_msg:
                    fail_closed_in_production(
                        "e2b",
                        f"Neither E2B cloud nor local Docker sandbox available: {exc}",
                        cause=exc,
                    )
                raise
            except Exception as exc:
                fail_closed_in_production(
                    "e2b",
                    f"Neither E2B cloud nor local Docker sandbox available: {exc}",
                    cause=exc,
                )

        # Path D: Simulated mode without CI_TEST_MODE — fail closed
        fail_closed_in_production(
            "e2b",
            "E2B_API_KEY not set and CI_TEST_MODE=1 not set; cannot execute command",
        )
        raise ProductionSafetyError(
            "E2B_API_KEY not set and CI_TEST_MODE=1 not set; cannot execute command"
        )
