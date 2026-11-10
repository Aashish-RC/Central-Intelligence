"""Co-Editing Conflict Resolver (Feature 6.38)

CRDT / Operational Transformation (OT) engine resolving concurrent real-time
document edits without silent overwrites or state divergent forks.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class OpType(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    RETAIN = "retain"


@dataclass
class TextOperation:
    """Atomic text edit operation."""
    op_type: OpType
    position: int
    text: str = ""       # Used for INSERT
    length: int = 0      # Used for DELETE
    client_id: str = "anon"
    revision: int = 0
    timestamp: float = 0.0


class ConflictResolver:
    """Operational Transformation conflict resolution engine for collaborative documents."""

    @staticmethod
    def apply_operation(document_text: str, op: TextOperation) -> str:
        """Apply an operation directly onto a string document."""
        pos = max(0, min(op.position, len(document_text)))

        if op.op_type == OpType.INSERT:
            return document_text[:pos] + op.text + document_text[pos:]
        elif op.op_type == OpType.DELETE:
            del_len = max(0, op.length or len(op.text))
            return document_text[:pos] + document_text[pos + del_len:]
        return document_text

    @staticmethod
    def transform(op_a: TextOperation, op_b: TextOperation) -> Tuple[TextOperation, TextOperation]:
        """Transform op_a against concurrent op_b such that applying (op_b then op_a')

        equals applying (op_a then op_b'). Neither user's edits are lost.
        """
        a_prime = copy.deepcopy(op_a)
        b_prime = copy.deepcopy(op_b)

        pos_a = op_a.position
        pos_b = op_b.position

        # Case 1: Both are INSERT
        if op_a.op_type == OpType.INSERT and op_b.op_type == OpType.INSERT:
            if pos_a < pos_b:
                b_prime.position += len(op_a.text)
            elif pos_a > pos_b:
                a_prime.position += len(op_b.text)
            else:
                # Same position tie-break deterministically by client_id
                if op_a.client_id < op_b.client_id:
                    b_prime.position += len(op_a.text)
                else:
                    a_prime.position += len(op_b.text)

        # Case 2: op_a is INSERT, op_b is DELETE
        elif op_a.op_type == OpType.INSERT and op_b.op_type == OpType.DELETE:
            del_len = op_b.length or len(op_b.text)
            if pos_a <= pos_b:
                b_prime.position += len(op_a.text)
            elif pos_a >= pos_b + del_len:
                a_prime.position -= del_len
            else:
                # Insert was inside deleted range; move insert to delete origin
                a_prime.position = pos_b

        # Case 3: op_a is DELETE, op_b is INSERT
        elif op_a.op_type == OpType.DELETE and op_b.op_type == OpType.INSERT:
            del_len = op_a.length or len(op_a.text)
            if pos_b <= pos_a:
                a_prime.position += len(op_b.text)
            elif pos_b >= pos_a + del_len:
                b_prime.position -= del_len
            else:
                # Delete encompasses insert position; extend delete range
                a_prime.length = del_len + len(op_b.text)

        # Case 4: Both are DELETE
        elif op_a.op_type == OpType.DELETE and op_b.op_type == OpType.DELETE:
            len_a = op_a.length or len(op_a.text)
            len_b = op_b.length or len(op_b.text)

            if pos_a + len_a <= pos_b:
                b_prime.position -= len_a
            elif pos_b + len_b <= pos_a:
                a_prime.position -= len_b
            else:
                # Overlapping deletes: shrink respective remaining spans
                overlap_start = max(pos_a, pos_b)
                overlap_end = min(pos_a + len_a, pos_b + len_b)
                overlap_len = max(0, overlap_end - overlap_start)

                if pos_a < pos_b:
                    a_prime.length = len_a - overlap_len
                    b_prime.position = pos_a
                    b_prime.length = len_b - overlap_len
                else:
                    b_prime.length = len_b - overlap_len
                    a_prime.position = pos_b
                    a_prime.length = len_a - overlap_len

        return a_prime, b_prime

    def resolve_concurrent_edits(
        self,
        base_text: str,
        op_user_a: TextOperation,
        op_user_b: TextOperation,
    ) -> str:
        """Merge two concurrent user edits without either user overwriting the other."""
        op_a_prime, op_b_prime = self.transform(op_user_a, op_user_b)

        # Path 1: Apply User A then transformed User B
        res_a_then_b = self.apply_operation(base_text, op_user_a)
        res_a_then_b = self.apply_operation(res_a_then_b, op_b_prime)

        # Path 2: Apply User B then transformed User A
        res_b_then_a = self.apply_operation(base_text, op_user_b)
        res_b_then_a = self.apply_operation(res_b_then_a, op_a_prime)

        # Both paths MUST converge to identical state (OT convergence property)
        assert res_a_then_b == res_b_then_a, f"OT divergence: '{res_a_then_b}' != '{res_b_then_a}'"
        return res_a_then_b

