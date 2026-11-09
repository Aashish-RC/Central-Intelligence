"""Unified Memory Manager (Engine Facade API) orchestrating the 3 tiers and 4 stitches."""

import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from memory.config import MemoryConfig, default_config, WorkingMemoryBackend, FactStoreBackend, VectorStoreBackend
from memory.core.models import (
    ContextPackage,
    FactCategory,
    FactItem,
    MemoryRecord,
    Turn,
    TurnRole,
    MemorySourcesView,
    utc_now,
)
from memory.core.interfaces import (
    BaseWorkingMemory,
    BaseFactStore,
    BaseVectorStore,
    BaseGraphStore,
    BaseEmbedder,
)
from memory.tiers.working.in_memory import InMemoryWorkingMemory
from memory.tiers.working.redis_adapter import RedisWorkingMemory
from memory.tiers.facts.sqlite_adapter import SQLiteFactStore
from memory.tiers.facts.postgres_adapter import PostgreSQLFactStore
from memory.tiers.semantic.qdrant_adapter import QdrantAdapter
from memory.tiers.semantic.chroma_adapter import ChromaAdapter
from memory.tiers.graph.memgraph_adapter import MemgraphAdapter
from memory.embeddings.embedder import get_embedder
from memory.stitches.extractor import FactExtractor
from memory.stitches.conflict_resolver import ConflictResolver
from memory.stitches.synthesizer import ContextSynthesizer
from memory.stitches.consolidation import ConsolidationEngine, ConsolidationResult
from memory.stitches.sources_view import MemorySourcesViewBuilder
from memory.integrity.poisoning_defense import (
    MemoryPoisoningDefense,
    MemoryPoisoningError,
    PoisoningDetectionResult,
    SecurityPolicyViolationError,
)
from memory.lessons import (
    LessonsLearnedExtractor,
    LessonStore,
    LessonRecord,
    LessonCategory,
)


class MemoryEngine:
    """Unified Facade API for the Fused Dynamic Memory Layer."""

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        working_memory: Optional[BaseWorkingMemory] = None,
        fact_store: Optional[BaseFactStore] = None,
        vector_store: Optional[BaseVectorStore] = None,
        graph_store: Optional[BaseGraphStore] = None,
        embedder: Optional[BaseEmbedder] = None,
        guardrails_client: Optional[Any] = None,
        poisoning_defense: Optional[MemoryPoisoningDefense] = None,
    ):
        self.config = config or default_config
        self.guardrails_client = guardrails_client
        self.poisoning_defense = poisoning_defense or MemoryPoisoningDefense()

        # Embedder
        self.embedder = embedder or get_embedder(self.config)

        # Tier 1: Working Memory
        if working_memory is not None:
            self.working = working_memory
        elif self.config.working_backend == WorkingMemoryBackend.REDIS:
            self.working = RedisWorkingMemory(
                redis_url=self.config.redis_url,
                ttl_seconds=self.config.session_ttl_seconds,
            )
        else:
            self.working = InMemoryWorkingMemory(wal_dir=self.config.wal_dir)

        # Tier 2: Fact Store
        if fact_store is not None:
            self.facts = fact_store
        elif self.config.fact_backend == FactStoreBackend.POSTGRES and self.config.postgres_url:
            self.facts = PostgreSQLFactStore(connection_url=self.config.postgres_url)
        else:
            self.facts = SQLiteFactStore(db_path=self.config.sqlite_path)

        # Tier 3: Semantic Vector Store
        if vector_store is not None:
            self.vectors = vector_store
        elif self.config.vector_backend == VectorStoreBackend.CHROMA:
            self.vectors = ChromaAdapter(
                persist_dir=self.config.chroma_path,
                collection_name=self.config.collection_name,
            )
        else:
            self.vectors = QdrantAdapter(
                location=self.config.qdrant_location,
                collection_name=self.config.collection_name,
                dim=self.embedder.dimension,
            )

        # Tier 4: Knowledge Graph Store
        if graph_store is not None:
            self.graph = graph_store
        else:
            self.graph = MemgraphAdapter(
                host=self.config.memgraph_host,
                port=self.config.memgraph_port,
                username=self.config.memgraph_username,
                password=self.config.memgraph_password,
            )

        # Stitches
        self.extractor = FactExtractor(config=self.config)
        self.resolver = ConflictResolver(fact_store=self.facts)
        self.synthesizer = ContextSynthesizer(config=self.config)
        self.consolidation = ConsolidationEngine(
            working_memory=self.working,
            fact_store=self.facts,
            vector_store=self.vectors,
            embedder=self.embedder,
            config=self.config,
        )

        # Feature 2.49: Lessons-Learned Subsystem
        self.lesson_extractor = LessonsLearnedExtractor()
        self.lesson_store = LessonStore(
            db_path=self.config.sqlite_path if hasattr(self.config, "sqlite_path") else None
        )

    def remember(
        self,
        user_id: str,
        text: str,
        session_id: Optional[str] = None,
        role: TurnRole = TurnRole.USER,
        project_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Record an incoming agent/user interaction into the memory hierarchy.
        
        Orchestration flow:
        1. Logs turn to Tier 1 Working Memory (if session_id provided).
        2. Stitch 1: Triage and extract atomic facts & summaries.
        3. Stitch 2: Cross-referencing UUID linked across SQL and vector payloads.
        4. Stitch 3: Conflict resolution & deduplication against active Tier 2 state.
        5. Writes archival memory to Tier 3 with dense vector embedding.
        """
        metadata = metadata or {}
        event_id = uuid4()

        # Feature 2.47: Memory Poisoning Defense Pre-Write Integrity Check
        if hasattr(self, "poisoning_defense") and self.poisoning_defense is not None:
            poison_res = self.poisoning_defense.check_memory(
                text=text,
                metadata=metadata,
                source=str(getattr(role, "value", role)),
            )
            if poison_res.is_poisoned:
                quarantine_id = self.poisoning_defense.quarantine(
                    text=text,
                    user_id=user_id,
                    result=poison_res,
                    metadata=metadata,
                )
                raise MemoryPoisoningError(
                    f"Memory write rejected by poisoning defense ({poison_res.threat_category}): "
                    f"{'; '.join(poison_res.reasons)} [quarantine_id={quarantine_id}]",
                    result=poison_res,
                )

        # Task 1.1 / W9: Guardrails Pre-Write Filter for Memory Store
        client = getattr(self, "guardrails_client", None)
        if client is not None:
            try:
                g_res = client.check(prompt=text, actor=user_id) if hasattr(client, "check") else client.analyze(text, actor=user_id)
                action = getattr(g_res, "action", "allow")
                if action == "redact" and getattr(g_res, "sanitized_prompt", None):
                    text = g_res.sanitized_prompt
                elif action in ("block", "crisis_intervention"):
                    raise SecurityPolicyViolationError(
                        f"Memory write rejected by guardrails policy ({action}): {getattr(g_res, 'reason', 'Blocked by policy')}"
                    )
            except Exception as ex:
                if isinstance(ex, SecurityPolicyViolationError):
                    raise
        else:
            try:
                from guardrails.client import GuardrailsClient
                client = GuardrailsClient()
                g_res = client.check(prompt=text, actor=user_id)
                if g_res.action == "redact" and g_res.sanitized_prompt:
                    text = g_res.sanitized_prompt
                elif g_res.action in ("block", "crisis_intervention"):
                    raise SecurityPolicyViolationError(
                        f"Memory write rejected by guardrails policy ({g_res.action}): {g_res.reason}"
                    )
            except ImportError:
                pass

        # Step 1: Append turn to Tier 1 Working Memory
        if session_id:
            turn = Turn(
                id=event_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                role=role,
                content=text,
                tokens=self.synthesizer.count_tokens(text),
                metadata=metadata,
            )
            self.working.append_turn(turn)

        # Step 2: Stitch 1 (Extraction)
        plan = self.extractor.extract_memory_plan(text=text, user_id=user_id)

        # Step 3 & 4: Stitch 3 (Conflict resolution against Tier 2)
        saved_facts: List[FactItem] = []
        if plan.facts_to_add or plan.keys_to_invalidate:
            for fact in plan.facts_to_add:
                fact.source_event_id = event_id
                fact.project_id = project_id
                fact.tenant_id = tenant_id
            saved_facts = self.resolver.resolve_and_apply(
                candidate_facts=plan.facts_to_add,
                keys_to_invalidate=plan.keys_to_invalidate,
            )

        # Step 5: Upsert archival memory to Tier 3
        archival_record_id = None
        if plan.archival_text:
            emb = self.embedder.embed_text(plan.archival_text)
            archival_record = MemoryRecord(
                id=event_id,
                tenant_id=tenant_id,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                text=plan.archival_text,
                embedding=emb,
                metadata={
                    "entities": plan.entities,
                    "event_type": role.value,
                    **metadata,
                },
            )
            self.vectors.upsert_vectors([archival_record])
            archival_record_id = str(event_id)

        # Step 6: Tier 4 Graph Store Sync
        graph_relationships = []
        if hasattr(self, "graph") and self.graph:
            for ent in plan.entities:
                try:
                    self.graph.add_entity(user_id=user_id, name=ent, project_id=project_id)
                except Exception:
                    pass

            for fact in saved_facts:
                if fact.category == FactCategory.RELATIONSHIP or any(
                    k in fact.key.lower() for k in ["manages", "reports_to", "works_at", "member_of", "part_of"]
                ):
                    try:
                        rel_name = fact.key.replace(" ", "_").upper()
                        rel_info = self.graph.add_relationship(
                            user_id=user_id,
                            source=user_id,
                            relation=rel_name,
                            target=fact.value,
                            properties={"fact_id": str(fact.id)},
                            project_id=project_id,
                        )
                        graph_relationships.append(rel_info)
                    except Exception:
                        pass

        return {
            "event_id": str(event_id),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "project_id": project_id,
            "session_id": session_id,
            "facts_saved": [f.model_dump() for f in saved_facts],
            "archival_record_id": archival_record_id,
            "entities": plan.entities,
            "graph_relationships": graph_relationships,
        }

    def recall(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        top_k: Optional[int] = None,
        tenant_id: str = "default",
    ) -> ContextPackage:
        """Recall concentrated context (< 500 tokens) for system prompt injection.
        
        Synthesizes:
        - Tier 1: Most recent conversation window for active session.
        - Tier 2: Ground-truth active user facts and preferences (project-isolated).
        - Tier 3: Top-K semantic archival matches (project-isolated).
        """
        k = top_k or self.config.top_k_semantic_matches

        # Tier 1: Working memory window
        working_turns: List[Turn] = []
        if session_id:
            working_turns = self.working.get_active_window(
                session_id=session_id,
                limit=self.config.working_window_turns,
            )

        # Tier 2: Active structured facts
        core_facts = self.facts.get_facts(user_id=user_id, active_only=True, project_id=project_id)
        # Touch facts to reinforce access frequency
        for f in core_facts:
            self.facts.touch_fact(f.id)

        # Tier 3: Semantic archival matches
        query_emb = self.embedder.embed_text(query)
        archival_hits = self.vectors.query_similar(
            user_id=user_id,
            query_embedding=query_emb,
            top_k=k,
            active_only=True,
            project_id=project_id,
        )

        start_t = time.perf_counter()
        # Stitch 4: Dynamic Synthesis with token budget limit
        result = self.synthesizer.synthesize(
            user_id=user_id,
            session_id=session_id,
            working_turns=working_turns,
            core_facts=core_facts,
            archival_memories=archival_hits,
            tenant_id=tenant_id,
        )

        # Task 1.2: Telemetry emission for memory retrieval
        try:
            from observability.core.tracer import TelemetryCollector
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            token_count = getattr(result, "token_count", 0)
            TelemetryCollector.get_instance().emit(
                module="memory",
                operation="memory_recall",
                duration_ms=duration_ms,
                status_code=200,
                token_usage={"total_tokens": token_count, "prompt_tokens": token_count, "completion_tokens": 0},
                metadata={"user_id": user_id, "tenant_id": tenant_id, "facts_count": len(getattr(result, "facts", []))},
            )
        except Exception:
            pass

        return result

    def consolidate(self, user_id: str, session_id: str) -> ConsolidationResult:
        """Execute REM Sleep consolidation cycle on a session."""
        return self.consolidation.consolidate_session(user_id=user_id, session_id=session_id)

    def get_active_facts(self, user_id: str, project_id: Optional[str] = None) -> List[FactItem]:
        """Fetch all currently active ground-truth facts for a user."""
        return self.facts.get_facts(user_id=user_id, active_only=True, project_id=project_id)

    def update_fact(self, fact_id: Any, new_value: str) -> Optional[FactItem]:
        """Update the value of an active fact with version tracking."""
        from uuid import UUID
        fid = fact_id if isinstance(fact_id, UUID) else UUID(str(fact_id))
        return self.facts.update_fact(fid, new_value)

    def delete_fact(self, fact_id: Any) -> bool:
        """Permanently delete a structured fact."""
        from uuid import UUID
        fid = fact_id if isinstance(fact_id, UUID) else UUID(str(fact_id))
        return self.facts.delete_fact(fid)

    def delete_archival_memory(self, record_id: Any) -> bool:
        """Permanently delete an archival memory vector."""
        from uuid import UUID
        rid = record_id if isinstance(record_id, UUID) else UUID(str(record_id))
        return self.vectors.delete(rid)

    def delete_all_user_memory(self, user_id: str) -> Dict[str, int]:
        """Erase all memory traces (facts and vectors) for a given user."""
        vector_count = self.vectors.delete_by_user(user_id)
        active_facts = self.facts.get_facts(user_id=user_id, active_only=False)
        deleted_facts = 0
        for f in active_facts:
            if self.facts.delete_fact(f.id):
                deleted_facts += 1
        return {"deleted_facts": deleted_facts, "deleted_vectors": vector_count}

    def get_memory_sources(self, user_id: str, project_id: str = "default") -> MemorySourcesView:
        """Generate full provenance view of all facts and archival memories."""
        facts = self.facts.get_facts(user_id=user_id, active_only=False, project_id=project_id)
        # Search all records for user and project
        query_emb = self.embedder.embed_text("project memory context")
        records = self.vectors.query_similar(
            user_id=user_id,
            query_embedding=query_emb,
            top_k=50,
            active_only=False,
            project_id=project_id,
        )
        return MemorySourcesViewBuilder.build(
            user_id=user_id,
            project_id=project_id,
            facts=facts,
            archival_records=records,
        )

    def add_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        properties: Optional[Dict[str, Any]] = None,
        project_id: str = "default",
    ) -> Dict[str, Any]:
        """Record an explicit entity relationship in Tier 4 Knowledge Graph."""
        return self.graph.add_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            properties=properties,
            project_id=project_id,
        )

    def delete_relationship(
        self,
        user_id: str,
        source: str,
        relation: str,
        target: str,
        project_id: Optional[str] = None,
    ) -> bool:
        """Remove a relationship in Tier 4 Knowledge Graph (e.g. on conflict resolution)."""
        return self.graph.delete_relationship(
            user_id=user_id,
            source=source,
            relation=relation,
            target=target,
            project_id=project_id,
        )

    def query_graph(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query on the Tier 4 Knowledge Graph."""
        return self.graph.execute_query(query=query, params=params)

    def multi_hop_query(
        self,
        user_id: str,
        start_entity: str,
        relation: Optional[str] = None,
        hops: int = 2,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Traverse multi-hop relationships starting from an entity."""
        return self.graph.multi_hop_query(
            user_id=user_id,
            start_entity=start_entity,
            relation=relation,
            hops=hops,
            project_id=project_id,
        )

    def store(
        self,
        user_id: str,
        text: str,
        session_id: Optional[str] = None,
        role: TurnRole = TurnRole.USER,
        project_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convenience alias for remember() supporting the store() interface."""
        return self.remember(
            user_id=user_id,
            text=text,
            session_id=session_id,
            role=role,
            project_id=project_id,
            metadata=metadata,
        )

    # --- Feature 2.49 / 7.27: Lessons Learned APIs ---

    def extract_and_store_lessons(self, turns: List[Turn]) -> List[LessonRecord]:
        """Extract actionable lessons from conversation history and save them."""
        lessons = self.lesson_extractor.extract_from_turns(turns)
        for lesson in lessons:
            self.lesson_store.save_lesson(lesson)
        return lessons

    def get_relevant_lessons(
        self,
        query: str,
        category: Optional[LessonCategory] = None,
        limit: int = 3,
    ) -> List[LessonRecord]:
        """Retrieve stored operational lessons relevant to a task query or command."""
        return self.lesson_store.query_lessons(query=query, category=category, limit=limit)
