"""Unit tests for Capability Expansion from Demonstration (Features 7.25, 7.26)."""

import pytest
from cognitive.learning.demonstration.capability_expander import (
    CapabilityExpander,
    SkillStatus,
)


def test_after_same_workflow_3_times_suggests_automating_it_and_user_approves():
    expander = CapabilityExpander(repeat_threshold=3)
    user = "engineer_sam"

    # Helper to simulate a repeatable multi-step workflow
    def perform_git_deploy_workflow():
        expander.record_action(user, "git_checkout", "release/v2.1", {"branch": "release/v2.1"})
        expander.record_action(user, "run_tests", "pytest", {"target": "unit"})
        expander.record_action(user, "docker_build", "central_intelligence:v2.1", {"tag": "latest"})
        return expander.complete_workflow(user)

    # Execution 1
    res1 = perform_git_deploy_workflow()
    assert res1 is None  # count = 1, threshold 3 not yet reached
    assert len(expander.list_suggested_skills(user)) == 0

    # Execution 2
    res2 = perform_git_deploy_workflow()
    assert res2 is None  # count = 2

    # Execution 3 -> Reaches threshold 3!
    candidate_skill = perform_git_deploy_workflow()
    assert candidate_skill is not None
    assert candidate_skill.occurrences == 3
    assert candidate_skill.status == SkillStatus.SUGGESTED
    assert len(candidate_skill.steps) == 3

    # Appears in suggestions
    suggested = expander.list_suggested_skills(user)
    assert len(suggested) == 1
    assert suggested[0].skill_id == candidate_skill.skill_id

    # User reviews and approves
    activated = expander.review_and_activate(
        skill_id=candidate_skill.skill_id,
        approved=True,
        notes="Automated git test and docker build approved for continuous integration.",
    )
    assert activated is True
    assert candidate_skill.status == SkillStatus.ACTIVATED

    # Now listed in active skills
    active_skills = expander.list_activated_skills(user)
    assert len(active_skills) == 1
    assert active_skills[0].skill_id == candidate_skill.skill_id


def test_user_rejection_of_suggested_skill():
    expander = CapabilityExpander(repeat_threshold=2)
    user = "designer_eva"

    for _ in range(2):
        expander.record_action(user, "export_figma", "frame_hero", {"format": "svg"})
        expander.record_action(user, "optimize_svg", "svgo", {"multipass": True})
        candidate = expander.complete_workflow(user)

    assert candidate is not None
    assert candidate.status == SkillStatus.SUGGESTED

    # User reviews and rejects
    rejected = expander.review_and_activate(
        skill_id=candidate.skill_id,
        approved=False,
        notes="Manual review preferred for vector optimization.",
    )
    assert rejected is False
    assert candidate.status == SkillStatus.REJECTED
    assert len(expander.list_activated_skills(user)) == 0
