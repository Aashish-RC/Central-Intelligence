"""Capability Expansion from Demonstration (Features 7.25, 7.26)

Observes repeated user actions and interaction sequences, automatically infers
recurring operational workflows, generates candidate executable skills,
and requires explicit human review and approval before activation.
"""

from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillStatus(str, Enum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    ACTIVATED = "activated"
    REJECTED = "rejected"


@dataclass
class UserAction:
    """An individual user operation or tool invocation."""
    action_type: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def fingerprint(self) -> str:
        param_keys = sorted(self.parameters.keys())
        return f"{self.action_type}:{self.target}:{','.join(param_keys)}"


@dataclass
class CandidateSkill:
    """A proposed automated skill synthesized from repeated demonstrations."""
    skill_id: str
    name: str
    user_id: str
    workflow_signature: str
    occurrences: int
    steps: List[Dict[str, Any]]
    status: SkillStatus = SkillStatus.SUGGESTED
    review_notes: str = ""
    created_at: float = field(default_factory=time.time)


class CapabilityExpander:
    """Records demonstrations, infers patterns, and generates automated skills."""

    def __init__(self, repeat_threshold: int = 3) -> None:
        self.repeat_threshold = repeat_threshold
        # user_id -> list of current ongoing actions
        self.active_traces: Dict[str, List[UserAction]] = {}
        # workflow_signature -> count of occurrences
        self.pattern_counts: Dict[str, int] = {}
        # skill_id -> CandidateSkill
        self.candidate_skills: Dict[str, CandidateSkill] = {}

    def record_action(
        self,
        user_id: str,
        action_type: str,
        target: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a user action into their current demonstration trace."""
        if user_id not in self.active_traces:
            self.active_traces[user_id] = []

        action = UserAction(
            action_type=action_type,
            target=target,
            parameters=parameters or {},
        )
        self.active_traces[user_id].append(action)

    def complete_workflow(self, user_id: str) -> Optional[CandidateSkill]:
        """Finalize a workflow trace, evaluate recurrence, and suggest automation if threshold met."""
        actions = self.active_traces.pop(user_id, [])
        if not actions or len(actions) < 2:
            return None

        # Build structural workflow signature
        step_fingerprints = [a.fingerprint() for a in actions]
        sig_str = " -> ".join(step_fingerprints)
        workflow_sig = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()[:12]

        self.pattern_counts[workflow_sig] = self.pattern_counts.get(workflow_sig, 0) + 1
        count = self.pattern_counts[workflow_sig]

        # Trigger skill automation proposal if threshold reached
        if count >= self.repeat_threshold:
            skill_id = f"skill_auto_{workflow_sig}"
            if skill_id not in self.candidate_skills:
                skill_name = f"Automated Workflow ({actions[0].action_type} to {actions[-1].action_type})"
                steps = [
                    {
                        "step_index": idx,
                        "action_type": a.action_type,
                        "target": a.target,
                        "parameters": a.parameters,
                    }
                    for idx, a in enumerate(actions, start=1)
                ]

                candidate = CandidateSkill(
                    skill_id=skill_id,
                    name=skill_name,
                    user_id=user_id,
                    workflow_signature=workflow_sig,
                    occurrences=count,
                    steps=steps,
                    status=SkillStatus.SUGGESTED,
                )
                self.candidate_skills[skill_id] = candidate
                return candidate
            else:
                self.candidate_skills[skill_id].occurrences = count

        return None

    def review_and_activate(
        self,
        skill_id: str,
        approved: bool,
        notes: str = "",
    ) -> bool:
        """Human review gate: approve or reject candidate skill prior to system activation."""
        if skill_id not in self.candidate_skills:
            return False

        skill = self.candidate_skills[skill_id]
        skill.review_notes = notes

        if approved:
            skill.status = SkillStatus.ACTIVATED
            return True
        else:
            skill.status = SkillStatus.REJECTED
            return False

    def list_suggested_skills(self, user_id: Optional[str] = None) -> List[CandidateSkill]:
        """List candidate skills waiting for human review."""
        return [
            s for s in self.candidate_skills.values()
            if s.status == SkillStatus.SUGGESTED and (not user_id or s.user_id == user_id)
        ]

    def list_activated_skills(self, user_id: Optional[str] = None) -> List[CandidateSkill]:
        """List active skills approved for execution."""
        return [
            s for s in self.candidate_skills.values()
            if s.status == SkillStatus.ACTIVATED and (not user_id or s.user_id == user_id)
        ]

