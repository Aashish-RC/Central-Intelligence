"""Abstract interfaces for Pheonix Skills and Plugin Packaging."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .models import (
    ExecutionResult,
    InstallationRecord,
    PackageBundle,
    PluginManifest,
    SkillManifest,
)


class BasePackager(ABC):
    """Interface for packaging skills and plugins into signed portable bundles."""

    @abstractmethod
    def package_skill(
        self, manifest: SkillManifest, files: Dict[str, str]
    ) -> PackageBundle:
        pass

    @abstractmethod
    def package_plugin(
        self, manifest: PluginManifest, files: Dict[str, str]
    ) -> PackageBundle:
        pass


class BaseInstaller(ABC):
    """Interface for validating, installing, and managing active packages."""

    @abstractmethod
    def install_package(
        self, bundle: PackageBundle, destination_root: str
    ) -> InstallationRecord:
        pass

    @abstractmethod
    def uninstall_package(self, package_id: str) -> bool:
        pass

    @abstractmethod
    def get_installed_package(self, package_id: str) -> Optional[InstallationRecord]:
        pass

    @abstractmethod
    def list_installed_packages(self) -> List[InstallationRecord]:
        pass


class BasePluginRunner(ABC):
    """Interface for hot-reloading and executing installed skills and plugins in sandbox runtime."""

    @abstractmethod
    def execute_skill(
        self, record: InstallationRecord, payload: str
    ) -> ExecutionResult:
        pass

    @abstractmethod
    def execute_plugin(
        self, record: InstallationRecord, target_skill: str, payload: str
    ) -> ExecutionResult:
        pass
