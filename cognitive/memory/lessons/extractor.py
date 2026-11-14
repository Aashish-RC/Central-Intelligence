"""Lessons-Learned Auto-Extractor.

Distills actionable procedural knowledge and preventative rules from:
1. Tool error -> correction -> success sequences.
2. Explicit human corrections ("No, that's wrong; always pass --clean").
3. Structured post-mortem notes and reflective summaries.

Features: 2.49, 7.27
"""

import re
from typing import List, Optional
from cognitive.memory.core.models import Turn, TurnRole
from .models import LessonCategory, LessonRecord


class LessonsLearnedExtractor:
    """Extracts operational lessons learned from conversation history and error traces."""

    USER_CORRECTION_PATTERNS = [
        re.compile(r"(?:no|nope|wrong|incorrect)[,\s]+(?:don't|do not|never)\s+([^.\n]+)", re.IGNORECASE),
        re.compile(r"(?:always remember to|make sure to|you should always)\s+([^.\n]+)", re.IGNORECASE),
        re.compile(r"(?:in the future|next time)[,\s]+(?:please\s+)?([^.\n]+)", re.IGNORECASE),
        re.compile(r"(?:don't use|stop using)\s+([^,\n]+?)[,\s]+use\s+([^.\n]+)", re.IGNORECASE),
    ]

    ERROR_INDICATORS = [
        "error:", "exception:", "traceback", "failed with exit code",
        "modulenotfounderror", "attributeerror", "typeerror", "404 not found",
        "connection refused", "permission denied", "command not found"
    ]

    STRUCTURED_LESSON_PATTERNS = [
        re.compile(r"lesson(?:s)?\s*learned\s*:\s*([^.\n]+)", re.IGNORECASE),
        re.compile(r"root\s*cause\s*:\s*([^.\n]+)", re.IGNORECASE),
        re.compile(r"rule\s*:\s*([^.\n]+)", re.IGNORECASE),
    ]

    def extract_from_turns(self, turns: List[Turn]) -> List[LessonRecord]:
        """Scans a conversation window and extracts distilled lessons."""
        lessons: List[LessonRecord] = []

        if not turns:
            return lessons

        # 1. Check for explicit user corrections
        for turn in turns:
            if turn.role == TurnRole.USER:
                extracted = self._extract_user_corrections(turn)
                lessons.extend(extracted)

        # 2. Check for tool error -> fix sequences
        for i in range(len(turns) - 1):
            curr_turn = turns[i]
            next_turn = turns[i + 1]

            content_lower = curr_turn.content.lower()
            has_error = any(ind in content_lower for ind in self.ERROR_INDICATORS)

            if has_error and next_turn.role in (TurnRole.ASSISTANT, TurnRole.TOOL):
                lesson = self._extract_error_recovery(curr_turn, next_turn)
                if lesson:
                    lessons.append(lesson)

        # 3. Check for structured reflection markers
        for turn in turns:
            extracted = self._extract_structured_reflection(turn)
            lessons.extend(extracted)

        # Deduplicate lessons by title and rule
        unique_lessons: List[LessonRecord] = []
        seen_rules = set()
        for l in lessons:
            key = l.rule.strip().lower()
            if key not in seen_rules:
                seen_rules.add(key)
                unique_lessons.append(l)

        return unique_lessons

    def extract_from_text(self, text: str, session_id: Optional[str] = None) -> List[LessonRecord]:
        """Convenience method to extract lessons from an arbitrary markdown/text trace."""
        synthetic_turn = Turn(
            session_id=session_id or "default_session",
            user_id="system",
            role=TurnRole.USER,
            content=text,
        )
        return self.extract_from_turns([synthetic_turn])

    def _extract_user_corrections(self, turn: Turn) -> List[LessonRecord]:
        results: List[LessonRecord] = []
        content = turn.content

        for pattern in self.USER_CORRECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                matched_text = match.group(0).strip()
                guideline = match.group(1).strip() if match.groups() else matched_text

                category = LessonCategory.USER_CORRECTION
                if "tool" in matched_text.lower() or "command" in matched_text.lower():
                    category = LessonCategory.TOOL_FAILURE
                elif "config" in matched_text.lower() or "env" in matched_text.lower():
                    category = LessonCategory.ENVIRONMENT_CONFIG

                words = re.findall(r"\b[A-Za-z0-9_-]{3,}\b", matched_text)
                trigger = " ".join(words[:4]) if words else "general"

                lesson = LessonRecord(
                    title=f"User Correction: {matched_text[:40]}...",
                    category=category,
                    trigger_context=trigger,
                    mistake=f"Prior behavior triggered user correction: '{turn.content[:80]}'",
                    resolution=f"Enforce user guidance: {matched_text}",
                    rule=f"Always adhere to: {guideline}",
                    confidence=0.95,
                    source_session_id=turn.session_id,
                )
                results.append(lesson)
        return results

    def _extract_error_recovery(self, error_turn: Turn, recovery_turn: Turn) -> Optional[LessonRecord]:
        err_line = ""
        for line in error_turn.content.splitlines():
            if any(ind in line.lower() for ind in self.ERROR_INDICATORS):
                err_line = line.strip()
                break
        if not err_line:
            err_line = error_turn.content[:100]

        category = LessonCategory.TOOL_FAILURE
        if "modulenotfound" in err_line.lower() or "import" in err_line.lower():
            category = LessonCategory.ENVIRONMENT_CONFIG
        elif "syntaxerror" in err_line.lower() or "attributeerror" in err_line.lower():
            category = LessonCategory.SYNTAX_BUG
        elif "404" in err_line.lower() or "api" in err_line.lower():
            category = LessonCategory.API_MISMATCH

        trigger_words = re.findall(r"\b[A-Za-z0-9_-]{3,}\b", err_line)
        trigger = " ".join(trigger_words[:3]) if trigger_words else "error_recovery"

        # Determine recovery rule from next turn
        rec_snippet = recovery_turn.content.splitlines()[0] if recovery_turn.content else "Fixed via retry"
        rule = f"When encountering '{err_line[:50]}', resolve by: {rec_snippet[:60]}"

        return LessonRecord(
            title=f"Error Recovery: {err_line[:35]}...",
            category=category,
            trigger_context=trigger,
            mistake=err_line,
            resolution=rec_snippet,
            rule=rule,
            confidence=0.85,
            source_session_id=error_turn.session_id,
        )

    def _extract_structured_reflection(self, turn: Turn) -> List[LessonRecord]:
        results: List[LessonRecord] = []
        for pattern in self.STRUCTURED_LESSON_PATTERNS:
            for match in pattern.finditer(turn.content):
                lesson_text = match.group(1).strip()
                if len(lesson_text) > 5:
                    results.append(
                        LessonRecord(
                            title=f"Reflective Lesson: {lesson_text[:35]}...",
                            category=LessonCategory.GENERAL,
                            trigger_context=lesson_text[:30],
                            mistake="Identified during post-execution reflection",
                            resolution=lesson_text,
                            rule=f"Operational guideline: {lesson_text}",
                            confidence=0.9,
                            source_session_id=turn.session_id,
                        )
                    )
        return results
