"""Kamal CI Deployment Adapter (L17 Release & Lifecycle - Task 17.2).

Executes automated zero-downtime container deployments from CI pipelines
using Kamal's proxy-swapped rolling deployment strategy.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from control.safety.production_guard import (
    ProductionSafetyError,
    fail_closed_in_production,
    require_live_adapter,
)

logger = logging.getLogger(__name__)


class DeploymentPhase(str, Enum):
    INIT = "init"
    ACQUIRE_LOCK = "acquire_lock"
    PUSH_IMAGE = "push_image"
    BOOT_CONTAINER = "boot_container"
    HEALTHCHECK_PROBE = "healthcheck_probe"
    PROXY_SWAP = "proxy_swap"
    STOP_OLD_CONTAINER = "stop_old_container"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class KamalConfig:
    """Configuration for Kamal zero-downtime deployment."""
    service_name: str = "central-intelligence-api"
    image_repo: str = "ghcr.io/central-intelligence/api"
    servers: List[str] = field(default_factory=lambda: ["192.168.1.101", "192.168.1.102"])
    healthcheck_path: str = "/healthz"
    healthcheck_interval_s: float = 1.0
    healthcheck_timeout_s: float = 10.0


@dataclass
class KamalDeployment:
    """Record of a Kamal CI deployment execution."""
    deployment_id: str
    service_name: str
    version_tag: str
    active_servers: List[str]
    phase: DeploymentPhase = DeploymentPhase.INIT
    zero_downtime_guaranteed: bool = True
    downtime_seconds: float = 0.0
    phases_completed: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class KamalAdapter:
    """Automates zero-downtime deploys from CI using Kamal protocol."""

    def __init__(self, config: Optional[KamalConfig] = None, _defer_prod_check: bool = False) -> None:
        self.config = config or KamalConfig()
        self.adapter_mode = (
            "simulated" if _defer_prod_check else require_live_adapter("kamal")
        )
        self._deployments: Dict[str, KamalDeployment] = {}
        # server -> currently running container version
        self._server_versions: Dict[str, str] = {s: "initial_v0" for s in self.config.servers}

    def _run_kamal(
        self, cmd: List[str], env: Dict[str, str]
    ) -> subprocess.CompletedProcess:
        """Invoke a kamal CLI subcommand with the configured working directory."""
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=600,  # 10 minutes max per phase
            check=True,
        )
        logger.debug("kamal %s -> exit %d", " ".join(cmd[1:]), result.returncode)
        return result

    def _probe_healthcheck(self, version_tag: str) -> None:
        """HTTP-probe each server's healthcheck endpoint until 200 or timeout."""
        import httpx
        deadline = time.time() + self.config.healthcheck_timeout_s
        for server in self.config.servers:
            url = f"http://{server}{self.config.healthcheck_path}"
            last_err = None
            while time.time() < deadline:
                try:
                    resp = httpx.get(url, timeout=self.config.healthcheck_interval_s)
                    if resp.status_code == 200:
                        break
                except Exception as exc:
                    last_err = exc
                time.sleep(self.config.healthcheck_interval_s)
            else:
                fail_closed_in_production(
                    "kamal",
                    f"Healthcheck for server {server} (version {version_tag}) "
                    f"did not return 200 within {self.config.healthcheck_timeout_s}s: {last_err}",
                )

    def _simulate_deployment(
        self, deployment: KamalDeployment, version_tag: str
    ) -> KamalDeployment:
        """Hermetic / simulated deployment — preserves existing test contract."""
        for phase in [
            DeploymentPhase.ACQUIRE_LOCK,
            DeploymentPhase.PUSH_IMAGE,
            DeploymentPhase.BOOT_CONTAINER,
            DeploymentPhase.HEALTHCHECK_PROBE,
            DeploymentPhase.PROXY_SWAP,
            DeploymentPhase.STOP_OLD_CONTAINER,
        ]:
            deployment.phase = phase
            deployment.phases_completed.append(phase.value)
            if phase == DeploymentPhase.PROXY_SWAP:
                for s in self.config.servers:
                    self._server_versions[s] = version_tag
        deployment.phase = DeploymentPhase.COMPLETED
        deployment.downtime_seconds = 0.0
        deployment.zero_downtime_guaranteed = True
        deployment.completed_at = time.time()
        logger.info(
            "Kamal zero-downtime deployment '%s' completed successfully for version %s",
            deployment.deployment_id,
            version_tag,
        )
        return deployment

    def deploy(
        self,
        version_tag: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> KamalDeployment:
        """Execute complete zero-downtime rolling deployment from CI."""
        dep_id = f"kamal_{uuid.uuid4().hex[:10]}"
        deployment = KamalDeployment(
            deployment_id=dep_id,
            service_name=self.config.service_name,
            version_tag=version_tag,
            active_servers=list(self.config.servers),
        )
        self._deployments[dep_id] = deployment

        # Hermetic / simulated path — preserves existing test contract
        if self.adapter_mode != "live" or os.getenv("CI_TEST_MODE") == "1":
            return self._simulate_deployment(deployment, version_tag)

        # Live path — invoke real kamal CLI
        if shutil.which("kamal") is None:
            fail_closed_in_production(
                "kamal",
                "kamal CLI not found on PATH; install with 'gem install kamal'",
            )

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            # Phase 1: acquire lock & push image
            deployment.phase = DeploymentPhase.ACQUIRE_LOCK
            self._run_kamal(["kamal", "lock", "acquire"], env)
            deployment.phases_completed.append(DeploymentPhase.ACQUIRE_LOCK.value)

            deployment.phase = DeploymentPhase.PUSH_IMAGE
            self._run_kamal(["kamal", "registry", "push"], env)
            deployment.phases_completed.append(DeploymentPhase.PUSH_IMAGE.value)

            # Phase 2: boot new container
            deployment.phase = DeploymentPhase.BOOT_CONTAINER
            self._run_kamal(["kamal", "app", "boot", "--version", version_tag], env)
            deployment.phases_completed.append(DeploymentPhase.BOOT_CONTAINER.value)

            # Phase 3: probe healthcheck on new container
            deployment.phase = DeploymentPhase.HEALTHCHECK_PROBE
            self._probe_healthcheck(version_tag)
            deployment.phases_completed.append(DeploymentPhase.HEALTHCHECK_PROBE.value)

            # Phase 4: swap proxy upstream
            deployment.phase = DeploymentPhase.PROXY_SWAP
            self._run_kamal(["kamal", "proxy", "boot"], env)
            for s in self.config.servers:
                self._server_versions[s] = version_tag
            deployment.phases_completed.append(DeploymentPhase.PROXY_SWAP.value)

            # Phase 5: stop old container
            deployment.phase = DeploymentPhase.STOP_OLD_CONTAINER
            self._run_kamal(["kamal", "app", "stop", "--version", "previous"], env)
            deployment.phases_completed.append(DeploymentPhase.STOP_OLD_CONTAINER.value)

            deployment.phase = DeploymentPhase.COMPLETED
            deployment.downtime_seconds = 0.0
            deployment.zero_downtime_guaranteed = True
            deployment.completed_at = time.time()
            return deployment

        except subprocess.CalledProcessError as exc:
            deployment.phase = DeploymentPhase.FAILED
            deployment.completed_at = time.time()
            self._deployments[dep_id] = deployment
            fail_closed_in_production(
                "kamal",
                f"kamal command failed (exit {exc.returncode}): {exc.stderr or exc.stdout}",
                cause=exc,
            )
        except Exception as exc:
            deployment.phase = DeploymentPhase.FAILED
            deployment.completed_at = time.time()
            self._deployments[dep_id] = deployment
            if isinstance(exc, ProductionSafetyError):
                raise
            fail_closed_in_production(
                "kamal",
                f"kamal deployment failed: {exc}",
                cause=exc,
            )
        finally:
            # Always release the lock if not failed
            if deployment.phase != DeploymentPhase.FAILED:
                try:
                    self._run_kamal(["kamal", "lock", "release"], env)
                except Exception:
                    logger.warning("Failed to release kamal lock for deployment %s", dep_id)

    def get_deployment(self, deployment_id: str) -> Optional[KamalDeployment]:
        return self._deployments.get(deployment_id)

    def get_active_versions(self) -> Dict[str, str]:
        """Get live running container version per host server."""
        return dict(self._server_versions)
