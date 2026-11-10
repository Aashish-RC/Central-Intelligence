"""Unit tests for Co-Editing Conflict Resolver (Feature 6.38)."""

import pytest
from cognitive.output.collaboration.conflict_resolver import (
    ConflictResolver,
    TextOperation,
    OpType,
)


def test_two_users_editing_same_document_dont_overwrite_each_other():
    resolver = ConflictResolver()
    base_text = "The quick fox jumps."

    # User 1 inserts 'brown ' at position 10 (after 'quick ')
    op_user_1 = TextOperation(
        op_type=OpType.INSERT,
        position=10,
        text="brown ",
        client_id="user_alice",
    )

    # Concurrent User 2 inserts 'lazy ' at position 16 (before 'fox')
    op_user_2 = TextOperation(
        op_type=OpType.INSERT,
        position=10,
        text="spotted ",
        client_id="user_bob",
    )

    merged = resolver.resolve_concurrent_edits(base_text, op_user_1, op_user_2)

    # Neither user's edit was overwritten!
    assert "brown " in merged
    assert "spotted " in merged
    assert "The quick " in merged
    assert "fox jumps." in merged


def test_concurrent_insert_and_delete_no_overwrite():
    resolver = ConflictResolver()
    base_text = "Hello beautiful world!"

    # User Alice deletes 'beautiful ' (pos 6, length 10)
    op_alice = TextOperation(
        op_type=OpType.DELETE,
        position=6,
        length=10,
        client_id="alice",
    )

    # User Bob concurrently inserts 'wonderful ' at end (pos 22)
    op_bob = TextOperation(
        op_type=OpType.INSERT,
        position=22,
        text=" Enjoy today.",
        client_id="bob",
    )

    merged = resolver.resolve_concurrent_edits(base_text, op_alice, op_bob)

    assert "beautiful" not in merged
    assert "Hello world! Enjoy today." == merged


def test_independent_concurrent_edits():
    resolver = ConflictResolver()
    base_text = "Alpha Beta Gamma"

    # User 1 edits beginning
    op1 = TextOperation(op_type=OpType.INSERT, position=0, text="Init: ", client_id="user_1")
    # User 2 edits end
    op2 = TextOperation(op_type=OpType.INSERT, position=16, text=" Done.", client_id="user_2")

    merged = resolver.resolve_concurrent_edits(base_text, op1, op2)
    assert merged == "Init: Alpha Beta Gamma Done."
