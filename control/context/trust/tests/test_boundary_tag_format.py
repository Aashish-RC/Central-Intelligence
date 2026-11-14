"""Regression test ensuring the canonical dual-boundary tag form matches docs."""

from pathlib import Path
from control.context.trust.untrusted_sandbox import UntrustedSandbox


def test_tag_uses_untrusted_content_not_untrusted_user_input():
    sandbox = UntrustedSandbox(content="hello", source="retrieval", trust="low")
    rendered = str(sandbox)
    assert "<untrusted_content" in rendered
    assert "</untrusted_content>" in rendered
    assert "<untrusted_user_input" not in rendered
    assert "</untrusted_user_input>" not in rendered


def test_tag_includes_source_and_trust_attributes():
    sandbox = UntrustedSandbox(content="x", source="tool_output", trust="medium")
    rendered = str(sandbox)
    assert 'source="tool_output"' in rendered
    assert 'trust="medium"' in rendered


def test_docs_do_not_reference_old_tag_form():
    # Grep the docs directory for the deprecated tag form
    docs_dir = Path(__file__).parents[4] / "docs"
    old_form = "untrusted_user_input"
    offenders = []
    for md in docs_dir.rglob("*.md"):
        if old_form in md.read_text(encoding="utf-8"):
            offenders.append(str(md.relative_to(docs_dir)))
    assert not offenders, f"Docs still reference deprecated tag form: {offenders}"

