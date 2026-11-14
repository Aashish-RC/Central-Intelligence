"""Portability Manager for Cross-Assistant Memory Migration (Features 2.46, 2.50)."""

from typing import Any, Dict, List, Optional, Union
from cognitive.memory.portability.models import (
    ImportStats,
    MemoryPortabilityFormat,
    StandardFactRecord,
    StandardTurnRecord,
)
from cognitive.memory.portability.translators import (
    BaseTranslator,
    ChatGPTTranslator,
    ClaudeTranslator,
    StandardCITranslator,
)


class MemoryPortabilityManager:
    """Orchestrates importing and exporting memory states across assistants."""

    def __init__(self):
        self._translators: Dict[MemoryPortabilityFormat, BaseTranslator] = {
            MemoryPortabilityFormat.CI_STANDARD: StandardCITranslator(),
            MemoryPortabilityFormat.CHATGPT: ChatGPTTranslator(),
            MemoryPortabilityFormat.CLAUDE: ClaudeTranslator(),
        }

    def get_translator(self, format_type: Union[str, MemoryPortabilityFormat]) -> BaseTranslator:
        fmt = MemoryPortabilityFormat(format_type)
        if fmt not in self._translators:
            raise ValueError(f"Unsupported memory portability format: {format_type}")
        return self._translators[fmt]

    def parse_import(
        self,
        raw_data: Any,
        source_format: Union[str, MemoryPortabilityFormat],
        user_id: str,
    ) -> ImportStats:
        """Parses imported conversation data into standardized records."""
        translator = self.get_translator(source_format)
        fmt = MemoryPortabilityFormat(source_format)

        try:
            turns, facts = translator.parse(raw_data, user_id=user_id)
            sessions = {t.session_id for t in turns if t.session_id}
            return ImportStats(
                format=fmt,
                turns_imported=len(turns),
                facts_imported=len(facts),
                sessions_discovered=len(sessions),
                success=True,
            )
        except Exception as ex:
            return ImportStats(
                format=fmt,
                turns_imported=0,
                facts_imported=0,
                sessions_discovered=0,
                success=False,
                errors=[str(ex)],
            )

    def import_into_engine(
        self,
        raw_data: Any,
        source_format: Union[str, MemoryPortabilityFormat],
        user_id: str,
        engine: Any,
    ) -> ImportStats:
        """Parses foreign assistant memory and persists it into a live MemoryEngine."""
        translator = self.get_translator(source_format)
        fmt = MemoryPortabilityFormat(source_format)
        errors: List[str] = []

        try:
            turns, facts = translator.parse(raw_data, user_id=user_id)
        except Exception as ex:
            return ImportStats(
                format=fmt,
                success=False,
                errors=[f"Failed to parse source payload: {ex}"],
            )

        turns_stored = 0
        facts_stored = 0
        sessions = set()

        for t in turns:
            try:
                engine.store(
                    user_id=user_id,
                    text=t.content,
                    session_id=t.session_id or "imported_session",
                    metadata=t.metadata,
                )
                turns_stored += 1
                if t.session_id:
                    sessions.add(t.session_id)
            except Exception as ex:
                errors.append(f"Turn store error: {ex}")

        # Store explicit facts if present in the import
        if hasattr(engine, "facts") and engine.facts is not None:
            for f in facts:
                try:
                    from cognitive.memory.tiers.facts.schema import FactItem
                    item = FactItem(
                        user_id=user_id,
                        subject=f.subject,
                        predicate=f.predicate,
                        object=f.object,
                        confidence_score=f.confidence_score,
                    )
                    if hasattr(engine.facts, "put_fact"):
                        engine.facts.put_fact(item)
                    elif hasattr(engine.facts, "save_fact"):
                        engine.facts.save_fact(item)
                    facts_stored += 1
                except Exception as ex:
                    errors.append(f"Fact store error: {ex}")

        return ImportStats(
            format=fmt,
            turns_imported=turns_stored,
            facts_imported=facts_stored,
            sessions_discovered=len(sessions),
            success=len(errors) == 0,
            errors=errors,
        )

    def export_from_engine(
        self,
        user_id: str,
        target_format: Union[str, MemoryPortabilityFormat],
        engine: Any,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reads user turns and facts from MemoryEngine and formats them for export."""
        translator = self.get_translator(target_format)

        turns: List[StandardTurnRecord] = []
        facts: List[StandardFactRecord] = []

        # Read turns from working memory
        if hasattr(engine, "working") and engine.working is not None:
            raw_turns = engine.working.get_active_window(session_id=session_id or "default")
            for t in raw_turns:
                turns.append(
                    StandardTurnRecord(
                        id=str(t.id),
                        role=getattr(t.role, "value", str(t.role)),
                        content=t.content,
                        session_id=t.session_id,
                        metadata=getattr(t, "metadata", {}),
                    )
                )

        # Read facts from facts store
        if hasattr(engine, "facts") and engine.facts is not None:
            if hasattr(engine.facts, "get_facts"):
                raw_facts = engine.facts.get_facts(user_id=user_id)
            elif hasattr(engine.facts, "list_facts"):
                raw_facts = engine.facts.list_facts(user_id=user_id)
            else:
                raw_facts = []

            for f in raw_facts:
                facts.append(
                    StandardFactRecord(
                        subject=f.subject,
                        predicate=f.predicate,
                        object=f.object,
                        confidence_score=getattr(f, "confidence_score", getattr(f, "confidence", 1.0)),
                    )
                )

        return translator.format(turns=turns, facts=facts, user_id=user_id)
