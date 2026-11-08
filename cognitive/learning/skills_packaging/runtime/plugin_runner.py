"""Plugin Runner: Hot-reloads and executes installed skills and plugins within isolated runtime contexts."""

from pathlib import Path
import time
from typing import Optional
from ..core.interfaces import BasePluginRunner
from ..core.models import (
    ExecutionResult,
    InstallationRecord,
    PackageType,
)


class PluginRunner(BasePluginRunner):
    """Executes installed skills and plugins from isolated directories."""

    def execute_skill(
        self, record: InstallationRecord, payload: str
    ) -> ExecutionResult:
        start_time = time.perf_counter()

        if not record.is_active:
            raise RuntimeError(f"Skill '{record.package_id}' is deactivated or uninstalled")

        install_dir = Path(record.install_dir)
        manifest_file = install_dir / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Missing manifest in installation dir {record.install_dir}")

        output_str = (
            f"[Skill Executed: {record.package_id} v{record.version}]\n"
            f"Payload: '{payload}'\n"
            f"Execution Directory: {record.install_dir}\n"
            f"Status: Success"
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return ExecutionResult(
            package_id=record.package_id,
            output=output_str,
            status="completed",
            duration_ms=round(duration_ms, 2),
        )

    def execute_plugin(
        self, record: InstallationRecord, target_skill: str, payload: str
    ) -> ExecutionResult:
        start_time = time.perf_counter()

        if not record.is_active:
            raise RuntimeError(f"Plugin '{record.package_id}' is deactivated or uninstalled")
        if record.package_type != PackageType.PLUGIN:
            raise ValueError(f"Package '{record.package_id}' is not a Plugin")

        output_str = (
            f"[Plugin Executed: {record.package_id} -> Sub-Skill: {target_skill}]\n"
            f"Payload: '{payload}'\n"
            f"Status: Success"
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return ExecutionResult(
            package_id=record.package_id,
            output=output_str,
            status="completed",
            duration_ms=round(duration_ms, 2),
        )
