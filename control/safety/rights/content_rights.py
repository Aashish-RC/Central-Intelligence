"""
Content Rights & Source Attribution Enforcement (Features 10.56, 10.57).

Features:
- 10.56: Prohibits reproduction of protected copyrighted material in model outputs.
  Detects verbatim copyrighted text passages (using n-gram matching & sliding window comparison)
  and redacts them before delivery to the user.
- 10.57: Enforces source attribution rules: when an output draws upon external sources
  or RAG knowledge, verifies attribution and automatically appends provenance tags/citations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("control.safety.rights.content_rights")


@dataclass
class ProtectedMaterial:
    """Registered protected copyrighted work."""
    material_id: str
    title: str
    holder: str
    text_sample: str
    min_matching_words: int = 8
    license_type: str = "All Rights Reserved"


@dataclass
class InfringementMatch:
    """Details of a detected verbatim copyright reproduction."""
    material_id: str
    title: str
    holder: str
    matched_passage: str
    word_count: int
    start_pos: int
    end_pos: int


@dataclass
class AttributionRecord:
    """Source attribution descriptor."""
    title: str
    holder: Optional[str] = None
    license: Optional[str] = None
    url: Optional[str] = None
    required: bool = True


@dataclass
class ContentRightsResult:
    """Evaluation result for outbound model generation."""
    is_safe: bool
    action: str  # "allow", "redact", "attribute", "redact_and_attribute"
    sanitized_output: str
    infringements: List[InfringementMatch] = field(default_factory=list)
    attributions_appended: List[str] = field(default_factory=list)
    reason: Optional[str] = None


class ContentRightsEnforcer:
    """
    Enforces copyright non-reproduction and source attribution on outbound generation (Layer 10 & Layer 4).
    """

    def __init__(self, min_verbatim_words: int = 8):
        self.min_verbatim_words = min_verbatim_words
        self._protected_registry: Dict[str, ProtectedMaterial] = {}
        self._tagger: Optional[Any] = None

    def register_protected_material(
        self,
        material_id: str,
        title: str,
        holder: str,
        text_sample: str,
        min_matching_words: Optional[int] = None,
        license_type: str = "All Rights Reserved",
    ) -> ProtectedMaterial:
        """Registers a known copyrighted work for verbatim reproduction monitoring."""
        mat = ProtectedMaterial(
            material_id=material_id,
            title=title,
            holder=holder,
            text_sample=text_sample,
            min_matching_words=min_matching_words or self.min_verbatim_words,
            license_type=license_type,
        )
        self._protected_registry[material_id] = mat
        return mat

    def _get_tagger(self) -> Any:
        if self._tagger is None:
            try:
                from cognitive.knowledge.provenance.tagger import LicenseProvenanceTagger
                self._tagger = LicenseProvenanceTagger()
            except ImportError:
                try:
                    from knowledge.provenance.tagger import LicenseProvenanceTagger
                    self._tagger = LicenseProvenanceTagger()
                except ImportError:
                    pass
        return self._tagger

    def detect_verbatim_reproduction(self, text: str) -> List[InfringementMatch]:
        """
        Scans generated output for verbatim reproduction of registered protected texts.
        Uses sliding n-gram matching across words.
        """
        if not text or not self._protected_registry:
            return []

        matches: List[InfringementMatch] = []
        text_clean = text.strip()

        for mat in self._protected_registry.values():
            sample_words = re.findall(r"\b\w+\b", mat.text_sample)
            n = mat.min_matching_words
            if len(sample_words) < n:
                continue

            # Generate n-word shingles from protected sample
            for i in range(len(sample_words) - n + 1):
                shingle = " ".join(sample_words[i : i + n])
                # Search case-insensitively in target text
                pattern = re.compile(r"\b" + re.escape(shingle) + r"\b", re.IGNORECASE)
                for found in pattern.finditer(text_clean):
                    matched_str = found.group(0)
                    # Extend matched passage if subsequent words also match
                    start_idx = found.start()
                    end_idx = found.end()
                    matches.append(
                        InfringementMatch(
                            material_id=mat.material_id,
                            title=mat.title,
                            holder=mat.holder,
                            matched_passage=matched_str,
                            word_count=len(matched_str.split()),
                            start_pos=start_idx,
                            end_pos=end_idx,
                        )
                    )

        # Deduplicate and merge contiguous/overlapping matches from the same material
        deduped: List[InfringementMatch] = []
        for m in sorted(matches, key=lambda x: (x.start_pos, x.end_pos)):
            if not deduped:
                deduped.append(m)
                continue

            last = deduped[-1]
            # If same material and overlapping or separated only by whitespace/punctuation
            gap = text_clean[last.end_pos : m.start_pos]
            if (
                m.material_id == last.material_id
                and m.start_pos <= last.end_pos + 2
                and (not gap or gap.isspace() or gap in ",;:- ")
            ):
                # Merge into contiguous match
                new_end = max(last.end_pos, m.end_pos)
                last.end_pos = new_end
                last.matched_passage = text_clean[last.start_pos : new_end]
                last.word_count = len(last.matched_passage.split())
            elif m.start_pos >= last.end_pos:
                deduped.append(m)

        return deduped

    def redact_infringing_text(self, text: str, infringements: List[InfringementMatch]) -> str:
        """Redacts verbatim copyrighted passages with compliant placeholder notices."""
        if not infringements:
            return text

        # Sort matches in reverse order of start position so replacements do not distort indices
        sorted_infringements = sorted(infringements, key=lambda x: x.start_pos, reverse=True)
        sanitized = text

        for inf in sorted_infringements:
            placeholder = f"[REDACTED: Verbatim Copyrighted Material from '{inf.title}' by {inf.holder}]"
            sanitized = sanitized[: inf.start_pos] + placeholder + sanitized[inf.end_pos :]

        return sanitized

    def enforce_attribution(
        self,
        text: str,
        sources: List[Dict[str, Any]],
    ) -> Tuple[str, List[str]]:
        """
        Ensures that if output relies on sources, clear attribution notices are present.
        If missing, appends formatted citation footer.
        """
        if not sources:
            return text, []

        tagger = self._get_tagger()
        missing_attributions: List[str] = []

        for src in sources:
            title = src.get("title", "Untitled Source")
            holder = src.get("holder") or src.get("author")
            license_str = src.get("license")
            url = src.get("url")

            # If license is provided or can be analyzed via L3 tagger
            if tagger and not license_str and "text" in src:
                try:
                    tag_res = tagger.analyze(src["text"])
                    license_str = tag_res.license_id
                except Exception:
                    pass

            # Check if source title or holder is already cited in text
            cited = False
            if title.lower() in text.lower():
                cited = True
            elif holder and holder.lower() in text.lower():
                cited = True

            if not cited:
                attrib_parts = [f"**{title}**"]
                if holder:
                    attrib_parts.append(f"by {holder}")
                if license_str:
                    attrib_parts.append(f"({license_str})")
                if url:
                    attrib_parts.append(f"<{url}>")
                missing_attributions.append(" ".join(attrib_parts))

        if not missing_attributions:
            return text, []

        # Append attribution footer
        footer = "\n\n---\n**Sources & Attribution:**\n" + "\n".join(f"- {a}" for a in missing_attributions)
        attributed_text = text.rstrip() + footer
        return attributed_text, missing_attributions

    def evaluate_output(
        self,
        output_text: str,
        sources: Optional[List[Dict[str, Any]]] = None,
    ) -> ContentRightsResult:
        """
        Comprehensive output rights enforcement:
        1. Checks for verbatim copyrighted reproduction and redacts (Feature 10.56).
        2. Checks for source attribution and appends citation notices if missing (Feature 10.57).
        """
        # 1. Verbatim copyright check
        infringements = self.detect_verbatim_reproduction(output_text)
        sanitized = self.redact_infringing_text(output_text, infringements)

        # 2. Attribution check
        appended_attribs: List[str] = []
        if sources:
            sanitized, appended_attribs = self.enforce_attribution(sanitized, sources)

        # Determine overall action & safety
        has_infringement = len(infringements) > 0
        has_new_attribs = len(appended_attribs) > 0

        if has_infringement and has_new_attribs:
            action = "redact_and_attribute"
            reason = f"Redacted {len(infringements)} copyrighted passage(s) and appended {len(appended_attribs)} source citation(s)."
        elif has_infringement:
            action = "redact"
            reason = f"Redacted {len(infringements)} verbatim copyrighted passage(s) to prevent infringement."
        elif has_new_attribs:
            action = "attribute"
            reason = f"Appended {len(appended_attribs)} source citation(s) for attribution compliance."
        else:
            action = "allow"
            reason = "Content rights and attribution standards fully satisfied."

        return ContentRightsResult(
            is_safe=not has_infringement,
            action=action,
            sanitized_output=sanitized,
            infringements=infringements,
            attributions_appended=appended_attribs,
            reason=reason,
        )


# Global default singleton
default_content_rights_enforcer = ContentRightsEnforcer()
