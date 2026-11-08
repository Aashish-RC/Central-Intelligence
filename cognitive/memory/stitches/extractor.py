"""Stitch 1: Triage & Fact Extractor (Structured LLM & Deterministic Pattern Parsing)."""

import json
import re
from typing import List, Optional
from uuid import UUID, uuid4

from memory.core.interfaces import BaseLLMExtractor
from memory.core.models import (
    FactItem,
    FactCategory,
    ExtractedMemoryPlan,
    utc_now,
)
from memory.config import MemoryConfig


CHIT_CHAT_PATTERNS = [
    r"^(hi|hello|hey|good morning|good evening|howdy)\b",
    r"^(thanks|thank you|thx|cheers)\b",
    r"^(ok|okay|sure|cool|got it|sounds good|understood)\b",
    r"^(yes|no|yep|nope|maybe)\b",
    r"^(what can you do|help me|can you help)\b",
    r"\bhow are you\b",
    r"\bhow's it going\b",
    r"\bwhat's up\b",
]


class FactExtractor(BaseLLMExtractor):
    """Extracts atomic facts, entities, and long-term archival summaries from raw events."""

    def __init__(self, config: Optional[MemoryConfig] = None):
        self._config = config
        self._openai_client = None
        if config and config.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=config.openai_api_key,
                    base_url=config.openai_base_url,
                )
            except Exception:
                self._openai_client = None

    def _is_ephemeral_chit_chat(self, text: str) -> bool:
        clean = text.lower().strip()
        if len(clean) < 4:
            return True
        for pattern in CHIT_CHAT_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                # If conversational greeting/smalltalk without substantial domain clauses
                words = clean.split()
                if len(words) <= 8 and not any(k in clean for k in ("write", "code", "use", "prefer", "live", "work", "moved")):
                    return True
        return False

    def _rule_based_extract(
        self,
        text: str,
        user_id: str,
        event_id: UUID,
        existing_facts: Optional[List[FactItem]] = None,
    ) -> ExtractedMemoryPlan:
        """Deterministic high-precision regex & rule extraction for local/offline execution."""
        facts_to_add: List[FactItem] = []
        keys_to_invalidate: List[str] = []
        entities: List[str] = []

        # 1. Location / Moving (e.g., "I moved from Berlin to Tokyo last week", "I live in Berlin")
        move_match = re.search(
            r"\b(moved from|relocated from)\s+([a-zA-Z]+)\s+to\s+([a-zA-Z]+)",
            text,
            re.IGNORECASE,
        )
        if move_match:
            old_loc = move_match.group(2).strip().capitalize()
            new_loc = move_match.group(3).strip().capitalize()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="location",
                    value=new_loc,
                    category=FactCategory.FACT,
                    source_event_id=event_id,
                )
            )
            keys_to_invalidate.append("location")
            entities.extend([old_loc, new_loc])
        else:
            live_match = re.search(
                r"\b(i live in|currently living in|located in|based in)\s+([a-zA-Z]+)",
                text,
                re.IGNORECASE,
            )
            if live_match:
                loc = live_match.group(2).strip().capitalize()
                facts_to_add.append(
                    FactItem(
                        id=uuid4(),
                        user_id=user_id,
                        key="location",
                        value=loc,
                        category=FactCategory.FACT,
                        source_event_id=event_id,
                    )
                )
                entities.append(loc)

        # 2. Programming Language & Tech Stacks
        lang_switch_match = re.search(
            r"\b(i only write|i use|switched to)\s+([a-zA-Z\+#]+)(\s+code)?\s+now[,\s]+(dropped|stopped using)\s+([a-zA-Z\+#]+)",
            text,
            re.IGNORECASE,
        )
        if lang_switch_match:
            new_lang = lang_switch_match.group(2).strip()
            old_lang = lang_switch_match.group(5).strip()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="preferred_language",
                    value=new_lang,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )
            keys_to_invalidate.append("preferred_language")
            entities.extend([new_lang, old_lang])
        else:
            lang_match = re.search(
                r"\b(i code in|i write|i prefer|(?:favorite|preferred) language is)\s+([a-zA-Z\+#]+)",
                text,
                re.IGNORECASE,
            )
            if lang_match:
                lang = lang_match.group(2).strip().capitalize()
                facts_to_add.append(
                    FactItem(
                        id=uuid4(),
                        user_id=user_id,
                        key="preferred_language",
                        value=lang,
                        category=FactCategory.PREFERENCE,
                        source_event_id=event_id,
                    )
                )
                entities.append(lang)

        # 2b. Cloud / Database Tech Stack
        cloud_match = re.search(
            r"\b(?:favorite|preferred) cloud(?: provider)? is\s+([a-zA-Z0-9\-_]+)",
            text,
            re.IGNORECASE,
        )
        if cloud_match:
            cloud = cloud_match.group(1).strip().upper()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="preferred_cloud",
                    value=cloud,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )
            entities.append(cloud)

        db_match = re.search(
            r"\b(?:favorite|preferred) database(?: engine)? (?:for this project )?is\s+([a-zA-Z0-9\-_]+)",
            text,
            re.IGNORECASE,
        )
        if db_match:
            db_name = db_match.group(1).strip()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="preferred_database",
                    value=db_name,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )
            entities.append(db_name)

        # 3. OS / Environment
        os_switch = re.search(
            r"\b(switched to|migrated to|now on)\s+(linux|mac|macos|windows|ubuntu)",
            text,
            re.IGNORECASE,
        )
        if os_switch:
            os_name = os_switch.group(2).strip().capitalize()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="operating_system",
                    value=os_name,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )
            keys_to_invalidate.append("operating_system")
            entities.append(os_name)
        elif re.search(r"\b(uses mac|on a mac|using macos|use linux|on linux)\b", text, re.IGNORECASE):
            os_match = re.search(r"\b(mac|macos|linux|windows)\b", text, re.IGNORECASE)
            val = os_match.group(1).capitalize() if os_match else "Linux"
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="operating_system",
                    value=val,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )
            entities.append(val)

        # 4. Identity / Name
        name_match = re.search(
            r"\b(my name is|call me)\s+([A-Z][a-zA-Z]+)\b",
            text,
            re.IGNORECASE,
        )
        if name_match:
            candidate_name = name_match.group(2).strip().capitalize()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="name",
                    value=candidate_name,
                    category=FactCategory.ENTITY,
                    source_event_id=event_id,
                )
            )
            entities.append(candidate_name)

        # 5. UI Preferences
        theme_match = re.search(r"\b(dark mode|light mode)\b", text, re.IGNORECASE)
        if theme_match:
            theme = theme_match.group(1).lower()
            facts_to_add.append(
                FactItem(
                    id=uuid4(),
                    user_id=user_id,
                    key="ui_theme",
                    value=theme,
                    category=FactCategory.PREFERENCE,
                    source_event_id=event_id,
                )
            )

        is_chit_chat = self._is_ephemeral_chit_chat(text)
        archival_text = None if is_chit_chat else text.strip()

        return ExtractedMemoryPlan(
            facts_to_add=facts_to_add,
            keys_to_invalidate=keys_to_invalidate,
            archival_text=archival_text,
            entities=list(set(entities)),
            summary=f"Turn processed: {len(facts_to_add)} facts identified." if facts_to_add else None,
        )

    def extract_memory_plan(
        self,
        text: str,
        user_id: str,
        existing_facts: Optional[List[FactItem]] = None,
    ) -> ExtractedMemoryPlan:
        event_id = uuid4()

        if self._openai_client is not None and not self._is_ephemeral_chit_chat(text):
            try:
                system_prompt = (
                    "You are a Memory Triage and Fact Extractor for an AI agent.\n"
                    "Extract atomic persistent facts, user preferences, relationships, and contradictions.\n"
                    "Return a JSON object conforming to:\n"
                    "{\n"
                    '  "facts": [{"key": string, "value": string, "category": "preference"|"rule"|"relationship"|"entity"|"constraint"|"fact"}],\n'
                    '  "invalidated_keys": [string],\n'
                    '  "entities": [string],\n'
                    '  "archival_summary": string or null\n'
                    "}"
                )
                res = self._openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"User ID: {user_id}\nInput: {text}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                raw = json.loads(res.choices[0].message.content or "{}")
                facts = [
                    FactItem(
                        id=uuid4(),
                        user_id=user_id,
                        key=f["key"].lower().replace(" ", "_"),
                        value=str(f["value"]),
                        category=FactCategory(f.get("category", "fact")),
                        source_event_id=event_id,
                    )
                    for f in raw.get("facts", [])
                ]
                return ExtractedMemoryPlan(
                    facts_to_add=facts,
                    keys_to_invalidate=raw.get("invalidated_keys", []),
                    archival_text=raw.get("archival_summary") or text,
                    entities=raw.get("entities", []),
                    summary=f"Extracted {len(facts)} facts via LLM.",
                )
            except Exception:
                pass

        return self._rule_based_extract(text, user_id, event_id, existing_facts)
