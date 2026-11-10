"""Adaptation Scope Applier (Feature 7.15)

Applies learned behavioral adaptations, prompt customizations, and domain policies
at their strict scoped level of authority:
USER -> APP -> PROFESSION -> ORGANIZATION -> GLOBAL.
Ensures user-level adaptations never bleed across user boundaries or tenant boundaries.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AdaptationScope(str, Enum):
    USER = "user"
    APP = "app"
    PROFESSION = "profession"
    ORG = "org"
    GLOBAL = "global"


@dataclass
class LearnedAdaptation:
    """A learned preference, custom guideline, or behavioral adjustment."""
    id: str
    scope: AdaptationScope
    target_id: str  # specific user_id, org_id, profession_id, or app_id
    adaptation_type: str  # e.g., 'style', 'prompt_injection', 'tool_restriction', 'parameter'
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 10  # higher numbers = higher precedence


class AdaptationScopeApplier:
    """Resolves and applies learned adaptations scoped to operational boundaries."""

    # Scope hierarchy precedence (higher index = higher precedence)
    SCOPE_PRECEDENCE = {
        AdaptationScope.GLOBAL: 1,
        AdaptationScope.ORG: 2,
        AdaptationScope.PROFESSION: 3,
        AdaptationScope.APP: 4,
        AdaptationScope.USER: 5,
    }

    def __init__(self) -> None:
        self.adaptations: Dict[str, LearnedAdaptation] = {}

    def register_adaptation(self, adaptation: LearnedAdaptation) -> None:
        """Register a new scoped adaptation."""
        self.adaptations[adaptation.id] = adaptation

    def get_applicable_adaptations(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        profession: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> List[LearnedAdaptation]:
        """Fetch all adaptations that match the caller's contextual scope."""
        applicable: List[LearnedAdaptation] = []

        for adapt in self.adaptations.values():
            if adapt.scope == AdaptationScope.GLOBAL:
                applicable.append(adapt)
            elif adapt.scope == AdaptationScope.USER and user_id and adapt.target_id == user_id:
                applicable.append(adapt)
            elif adapt.scope == AdaptationScope.ORG and org_id and adapt.target_id == org_id:
                applicable.append(adapt)
            elif adapt.scope == AdaptationScope.PROFESSION and profession and adapt.target_id.lower() == profession.lower():
                applicable.append(adapt)
            elif adapt.scope == AdaptationScope.APP and app_id and adapt.target_id == app_id:
                applicable.append(adapt)

        # Sort by scope hierarchy and then custom priority
        applicable.sort(
            key=lambda a: (self.SCOPE_PRECEDENCE[a.scope], a.priority),
            reverse=True,
        )
        return applicable

    def apply_to_prompt(
        self,
        base_prompt: str,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        profession: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> str:
        """Enrich a base prompt by applying scoped adaptation rules in hierarchical order."""
        adaptations = self.get_applicable_adaptations(
            user_id=user_id,
            org_id=org_id,
            profession=profession,
            app_id=app_id,
        )

        modifications: List[str] = []
        for adapt in adaptations:
            if "prompt_suffix" in adapt.payload:
                modifications.append(f"[{adapt.scope.value.upper()}:{adapt.target_id}] {adapt.payload['prompt_suffix']}")
            elif "style" in adapt.payload:
                modifications.append(f"Style Directive ({adapt.scope.value}): {adapt.payload['style']}")

        if not modifications:
            return base_prompt

        return f"{base_prompt}\n\nScoped Behavioral Adaptations:\n" + "\n".join(modifications)
