"""Custom Scorer Definitions (Layer 11: Evaluation & Quality, Feature 11.02).

Provides programmatic, schema-validated, and weighted composite scorers for evaluation datasets.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ScorerResult:
    """Outcome of evaluating a single candidate prediction against target criteria."""
    score: float  # 0.0 to 1.0
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class BaseScorer(ABC):
    """Abstract base scorer interface."""

    @abstractmethod
    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        """Calculates evaluation score."""
        pass


class ExactMatchScorer(BaseScorer):
    """Evaluates case-sensitive or insensitive exact equality."""

    def __init__(self, case_sensitive: bool = False, strip_whitespace: bool = True):
        self.case_sensitive = case_sensitive
        self.strip_whitespace = strip_whitespace

    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        if reference is None:
            return ScorerResult(score=0.0, passed=False, reason="Missing reference string")

        p = prediction.strip() if self.strip_whitespace else prediction
        r = reference.strip() if self.strip_whitespace else reference

        if not self.case_sensitive:
            p = p.lower()
            r = r.lower()

        match = p == r
        return ScorerResult(
            score=1.0 if match else 0.0,
            passed=match,
            details={"prediction": prediction, "reference": reference},
            reason="Matched exactly" if match else "Exact match failed",
        )


class ContainsAllScorer(BaseScorer):
    """Evaluates whether all required keywords/phrases appear in the prediction."""

    def __init__(self, required_terms: Optional[List[str]] = None, case_sensitive: bool = False):
        self.required_terms = required_terms or []
        self.case_sensitive = case_sensitive

    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        terms = list(self.required_terms)
        if metadata and "required_terms" in metadata:
            terms.extend(metadata["required_terms"])

        if not terms:
            return ScorerResult(score=1.0, passed=True, reason="No required terms specified")

        target = prediction if self.case_sensitive else prediction.lower()
        matched = []
        missing = []

        for t in terms:
            check_term = t if self.case_sensitive else t.lower()
            if check_term in target:
                matched.append(t)
            else:
                missing.append(t)

        score = len(matched) / len(terms)
        passed = len(missing) == 0

        return ScorerResult(
            score=score,
            passed=passed,
            details={"matched": matched, "missing": missing},
            reason="All terms found" if passed else f"Missing terms: {missing}",
        )


class RegexScorer(BaseScorer):
    """Evaluates whether prediction satisfies regex pattern."""

    def __init__(self, pattern: str, flags: int = re.IGNORECASE):
        self.pattern = pattern
        self.flags = flags
        self.compiled = re.compile(pattern, flags)

    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        match = bool(self.compiled.search(prediction))
        return ScorerResult(
            score=1.0 if match else 0.0,
            passed=match,
            details={"pattern": self.pattern},
            reason="Regex matched" if match else f"Did not match pattern {self.pattern}",
        )


class JsonSchemaScorer(BaseScorer):
    """Evaluates whether prediction is valid JSON matching expected schema keys."""

    def __init__(self, required_keys: Optional[List[str]] = None):
        self.required_keys = required_keys or []

    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        try:
            # Strip markdown json codeblocks if present
            cleaned = prediction.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
        except Exception as exc:
            return ScorerResult(score=0.0, passed=False, reason=f"Invalid JSON: {exc}")

        if not isinstance(data, dict):
            return ScorerResult(score=0.5, passed=False, reason="Parsed JSON is not an object/dict")

        req_keys = list(self.required_keys)
        if metadata and "required_keys" in metadata:
            req_keys.extend(metadata["required_keys"])

        if not req_keys:
            return ScorerResult(score=1.0, passed=True, reason="Valid JSON object")

        missing = [k for k in req_keys if k not in data]
        score = (len(req_keys) - len(missing)) / len(req_keys)
        passed = len(missing) == 0

        return ScorerResult(
            score=score,
            passed=passed,
            details={"missing_keys": missing},
            reason="All schema keys present" if passed else f"Missing keys: {missing}",
        )


class CompositeScorer(BaseScorer):
    """Weighted composite scorer aggregating multiple criteria."""

    def __init__(self, scorers: List[tuple[BaseScorer, float]], pass_threshold: float = 0.8):
        self.scorers = scorers
        self.pass_threshold = pass_threshold
        # Normalize weights
        total_weight = sum(w for _, w in scorers) or 1.0
        self.normalized_scorers = [(s, w / total_weight) for s, w in scorers]

    def score(self, prediction: str, reference: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ScorerResult:
        sub_results = []
        composite_score = 0.0

        for scorer, weight in self.normalized_scorers:
            res = scorer.score(prediction, reference, metadata)
            sub_results.append({"scorer": scorer.__class__.__name__, "result": res, "weight": weight})
            composite_score += res.score * weight

        passed = composite_score >= self.pass_threshold
        return ScorerResult(
            score=round(composite_score, 4),
            passed=passed,
            details={"sub_results": sub_results, "threshold": self.pass_threshold},
            reason="Threshold met" if passed else f"Score {composite_score:.2f} below {self.pass_threshold}",
        )

