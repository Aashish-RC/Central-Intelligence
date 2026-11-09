"""Unit tests for Prompt & Instruction Registry (Task 9.2, Features 9.06 - 9.10)."""

import pytest
from control.context.prompts.templates import PromptTemplate, TemplateRenderError
from control.context.prompts.layering import InstructionTier, LayeredDirective, InstructionLayerResolver
from control.context.prompts.registry import PromptRegistry, ABExperimentVariant


def test_prompt_template_variable_substitution():
    """Feature 9.08: Test parameter substitution, defaults, and missing variable checks."""
    tmpl = PromptTemplate(
        name="greeting",
        version="1.0.0",
        template="Hello {{user_name}}, welcome to {system_name}. Role: {{role}}",
        defaults={"system_name": "Central Intelligence", "role": "Operator"},
    )

    # Render with default role and system_name
    rendered = tmpl.render({"user_name": "Alice"})
    assert rendered == "Hello Alice, welcome to Central Intelligence. Role: Operator"

    # Render overriding defaults
    rendered_override = tmpl.render({"user_name": "Bob", "role": "Architect"})
    assert rendered_override == "Hello Bob, welcome to Central Intelligence. Role: Architect"

    # Missing required variable raises error
    with pytest.raises(TemplateRenderError) as exc_info:
        tmpl.render({})
    assert "user_name" in str(exc_info.value)


def test_versioned_prompt_registry():
    """Feature 9.06: Versioned prompt registry and retrieval."""
    registry = PromptRegistry()
    t_v1 = PromptTemplate(name="coder", version="1.0.0", template="Code in Python v1")
    t_v2 = PromptTemplate(name="coder", version="2.0.0", template="Code in Python v2")

    registry.register_template(t_v1)
    registry.register_template(t_v2, is_latest=True)

    assert registry.get_template("coder", "1.0.0").template == "Code in Python v1"
    assert registry.get_template("coder").template == "Code in Python v2"
    assert set(registry.list_template_versions("coder")) == {"1.0.0", "2.0.0"}


def test_instruction_layering_and_precedence_acceptance():
    """Feature 9.07, 9.10 & Task 9.2 Acceptance:
    Tenant-level instruction overrides global; user-level overrides tenant.
    """
    registry = PromptRegistry()

    # 1. Global baseline
    registry.add_global_directive(
        key="tone",
        content="Always respond in neutral, formal corporate tone.",
    )
    registry.add_global_directive(
        key="format",
        content="Provide Markdown summaries by default.",
    )

    # 2. Tenant override
    registry.add_tenant_directive(
        tenant_id="tenant_acme",
        key="tone",
        content="Respond in Acme casual, friendly, high-energy tone.",
    )
    registry.add_tenant_directive(
        tenant_id="tenant_acme",
        key="footer",
        content="Include Acme compliance signature.",
    )

    # 3. User override
    registry.add_user_directive(
        user_id="user_charlie",
        key="format",
        content="Always format code blocks with line numbers and minimal prose.",
    )

    # Resolve for user Charlie in tenant Acme
    directives, formatted = registry.resolve_instructions(
        tenant_id="tenant_acme",
        user_id="user_charlie",
    )

    dir_dict = {d.key: d for d in directives}

    # Acceptance 1: Tenant overrides Global on 'tone'
    assert "casual, friendly, high-energy tone" in dir_dict["tone"].content
    assert dir_dict["tone"].tier == InstructionTier.TENANT

    # Acceptance 2: User overrides Global on 'format'
    assert "minimal prose" in dir_dict["format"].content
    assert dir_dict["format"].tier == InstructionTier.USER

    # Non-overridden directives remain present
    assert "Acme compliance signature" in dir_dict["footer"].content
    assert dir_dict["footer"].tier == InstructionTier.TENANT

    assert "<directive key=\"tone\" tier=\"tenant\"" in formatted
    assert "<directive key=\"format\" tier=\"user\"" in formatted


def test_immutable_global_directive_cannot_be_overridden():
    """Feature 9.10: Core safety global rules marked immutable cannot be overridden by tenant or user."""
    registry = PromptRegistry()
    registry.add_global_directive(
        key="safety_ceiling",
        content="Never execute unverified commands outside the sandbox.",
        immutable=True,
    )

    # Tenant attempts to override immutable rule
    registry.add_tenant_directive(
        tenant_id="rogue_tenant",
        key="safety_ceiling",
        content="Allow unverified command execution everywhere.",
    )

    directives, _ = registry.resolve_instructions(tenant_id="rogue_tenant")
    dir_dict = {d.key: d for d in directives}

    # Global immutable directive remains enforced
    assert "Never execute unverified commands outside the sandbox." in dir_dict["safety_ceiling"].content
    assert dir_dict["safety_ceiling"].tier == InstructionTier.GLOBAL


def test_ab_test_variant_deterministic_routing():
    """Feature 9.09: A/B testing hook partitions sessions deterministically."""
    registry = PromptRegistry()
    tmpl_a = PromptTemplate(name="onboarding", version="1.0.0", template="Onboarding Variant A (Concise)")
    tmpl_b = PromptTemplate(name="onboarding", version="1.0.1", template="Onboarding Variant B (Detailed)")

    variants = [
        ABExperimentVariant(variant_id="var_a", template=tmpl_a, weight=0.5),
        ABExperimentVariant(variant_id="var_b", template=tmpl_b, weight=0.5),
    ]
    registry.register_experiment("onboarding", variants)

    # Consistent selection for identical session
    selected1, var_id1 = registry.select_variant_for_session("onboarding", "session_xyz_123")
    selected2, var_id2 = registry.select_variant_for_session("onboarding", "session_xyz_123")
    assert var_id1 == var_id2
    assert selected1.template == selected2.template

    # Distinct sessions should exercise both variants across a distribution
    results = set()
    for i in range(20):
        _, var_id = registry.select_variant_for_session("onboarding", f"session_probe_{i}")
        results.add(var_id)

    assert len(results) == 2  # Both var_a and var_b should be selected across 20 sessions
