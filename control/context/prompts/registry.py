"""Versioned Prompt & Instruction Registry (Layer 9, Features 9.06, 9.09)."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from control.context.prompts.templates import PromptTemplate
from control.context.prompts.layering import (
    InstructionTier,
    LayeredDirective,
    InstructionLayerResolver,
)


@dataclass
class ABExperimentVariant:
    """Represents an active prompt variant under A/B test (9.09)."""
    variant_id: str
    template: PromptTemplate
    weight: float = 0.5  # Traffic split weight
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptRegistry:
    """Centralized, versioned prompt template & layered instruction repository."""

    def __init__(self):
        # Maps template_name -> { version_str -> PromptTemplate }
        self._templates: Dict[str, Dict[str, PromptTemplate]] = {}
        # Maps template_name -> latest_version_str
        self._latest_versions: Dict[str, str] = {}
        # Multi-tier directives: layer -> list of LayeredDirective
        self._global_directives: List[LayeredDirective] = []
        self._tenant_directives: Dict[str, List[LayeredDirective]] = {}  # tenant_id -> directives
        self._app_directives: Dict[str, List[LayeredDirective]] = {}     # app_id -> directives
        self._user_directives: Dict[str, List[LayeredDirective]] = {}    # user_id -> directives
        # A/B experiments: template_name -> List[ABExperimentVariant]
        self._experiments: Dict[str, List[ABExperimentVariant]] = {}

    def register_template(self, template: PromptTemplate, is_latest: bool = True) -> None:
        """Feature 9.06: Register a versioned prompt template."""
        name = template.name
        version = template.version
        if name not in self._templates:
            self._templates[name] = {}
        self._templates[name][version] = template
        if is_latest or name not in self._latest_versions:
            self._latest_versions[name] = version

    def get_template(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        """Retrieve a specific or latest version of a template."""
        if name not in self._templates:
            return None
        ver = version or self._latest_versions.get(name)
        if not ver:
            return None
        return self._templates[name].get(ver)

    def list_template_versions(self, name: str) -> List[str]:
        return list(self._templates.get(name, {}).keys())

    # --- Directives & Multi-Tier Layering (9.07, 9.10) ---

    def add_global_directive(self, key: str, content: str, immutable: bool = False) -> None:
        """Add a global system instruction."""
        d = LayeredDirective(key=key, content=content, tier=InstructionTier.GLOBAL, immutable=immutable)
        self._global_directives = [x for x in self._global_directives if x.key != key] + [d]

    def add_tenant_directive(self, tenant_id: str, key: str, content: str) -> None:
        """Add tenant-level instruction override."""
        d = LayeredDirective(key=key, content=content, tier=InstructionTier.TENANT, scope_id=tenant_id)
        if tenant_id not in self._tenant_directives:
            self._tenant_directives[tenant_id] = []
        self._tenant_directives[tenant_id] = [x for x in self._tenant_directives[tenant_id] if x.key != key] + [d]

    def add_app_directive(self, app_id: str, key: str, content: str) -> None:
        """Add application-specific instruction."""
        d = LayeredDirective(key=key, content=content, tier=InstructionTier.APP, scope_id=app_id)
        if app_id not in self._app_directives:
            self._app_directives[app_id] = []
        self._app_directives[app_id] = [x for x in self._app_directives[app_id] if x.key != key] + [d]

    def add_user_directive(self, user_id: str, key: str, content: str) -> None:
        """Add user-specific instruction override."""
        d = LayeredDirective(key=key, content=content, tier=InstructionTier.USER, scope_id=user_id)
        if user_id not in self._user_directives:
            self._user_directives[user_id] = []
        self._user_directives[user_id] = [x for x in self._user_directives[user_id] if x.key != key] + [d]

    def resolve_instructions(
        self,
        tenant_id: Optional[str] = None,
        app_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[List[LayeredDirective], str]:
        """Resolves instructions across all layers applying precedence rules (9.10)."""
        tenant_dirs = self._tenant_directives.get(tenant_id, []) if tenant_id else []
        app_dirs = self._app_directives.get(app_id, []) if app_id else []
        user_dirs = self._user_directives.get(user_id, []) if user_id else []

        resolved = InstructionLayerResolver.resolve(
            global_directives=self._global_directives,
            tenant_directives=tenant_dirs,
            app_directives=app_dirs,
            user_directives=user_dirs,
        )
        formatted = InstructionLayerResolver.format_resolved_directives(resolved)
        return resolved, formatted

    # --- A/B Testing Hooks (9.09) ---

    def register_experiment(self, template_name: str, variants: List[ABExperimentVariant]) -> None:
        """Feature 9.09: Configure A/B experiment variants for a template."""
        self._experiments[template_name] = variants

    def select_variant_for_session(
        self,
        template_name: str,
        session_id: str,
    ) -> Tuple[PromptTemplate, str]:
        """Feature 9.09: Deterministically assigns a session to an A/B test variant.

        Uses stable hash partitioning so that a session consistently interacts with the
        same prompt variant during evaluation (measured by L11).
        """
        variants = self._experiments.get(template_name)
        if not variants:
            template = self.get_template(template_name)
            if not template:
                raise KeyError(f"Template '{template_name}' not registered.")
            return template, "control"

        # Hash session_id to float [0.0, 1.0)
        h = int(hashlib.sha256(session_id.encode("utf-8")).hexdigest(), 16)
        ratio = (h % 10000) / 10000.0

        cumulative = 0.0
        total_weight = sum(v.weight for v in variants)
        for v in variants:
            normalized_weight = v.weight / max(0.0001, total_weight)
            cumulative += normalized_weight
            if ratio <= cumulative:
                return v.template, v.variant_id

        # Fallback to last variant
        return variants[-1].template, variants[-1].variant_id
