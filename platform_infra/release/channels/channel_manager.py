"""Per-App Release Channels & Scoped Component Manifests (L17 Release - Feature 17.11).

Assigns each application to an independent release track (e.g. stable, beta, canary)
and computes filtered component version manifests scoped strictly to the components
that application consumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class AppChannelBinding:
    """Application subscription to a release channel and component subset."""

    app_id: str
    channel: str
    used_components: Set[str] = field(default_factory=set)
    pinned_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class ChannelManifest:
    """Resolved per-app deployment manifest scoped to its channel & dependencies."""

    app_id: str
    channel: str
    component_versions: Dict[str, str]


class ReleaseChannelManager:
    """Manages channel catalogs and scoped per-app component resolution."""

    def __init__(self) -> None:
        self._channel_versions: Dict[str, Dict[str, str]] = {}
        self._apps: Dict[str, AppChannelBinding] = {}

    def publish_to_channel(self, channel: str, component: str, version: str) -> None:
        """Register or update a component version on a release channel."""
        self._channel_versions.setdefault(channel, {})[component] = version

    def register_app(
        self,
        app_id: str,
        channel: str,
        used_components: List[str] | Set[str],
        pinned_overrides: Dict[str, str] | None = None,
    ) -> AppChannelBinding:
        """Bind an application to a channel and declare the components it uses."""
        binding = AppChannelBinding(
            app_id=app_id,
            channel=channel,
            used_components=set(used_components),
            pinned_overrides=dict(pinned_overrides or {}),
        )
        self._apps[app_id] = binding
        return binding

    def promote_app(self, app_id: str, new_channel: str) -> AppChannelBinding:
        """Switch an existing application to a different release channel."""
        binding = self._apps[app_id]
        binding.channel = new_channel
        return binding

    def resolve_manifest(self, app_id: str) -> ChannelManifest:
        """Resolve only the component versions used by `app_id` on its assigned channel."""
        binding = self._apps[app_id]
        catalog = self._channel_versions.get(binding.channel, {})
        resolved: Dict[str, str] = {}
        for comp in sorted(binding.used_components):
            if comp in binding.pinned_overrides:
                resolved[comp] = binding.pinned_overrides[comp]
            elif comp in catalog:
                resolved[comp] = catalog[comp]
        return ChannelManifest(
            app_id=app_id,
            channel=binding.channel,
            component_versions=resolved,
        )

