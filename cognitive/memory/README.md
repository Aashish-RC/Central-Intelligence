# Pheonix Fused Dynamic Memory Layer

A modular, production-grade **Fused Dynamic Memory Layer for AI Agents**, fusing the 3-tier cognitive hierarchy of **Letta** with the automated background fact extraction and conflict resolution of **Mem0**, backed by **Redis/WAL**, **SQLite/PostgreSQL**, and **Qdrant/Chroma**.

---

## 1. Architectural Highlights

- **3-Tier Cognitive Hierarchy:**
  - **Tier 1: Working Memory:** Sub-millisecond session cache (In-Memory with Write-Ahead Logging or Redis) for active conversational scratchpads.
  - **Tier 2: Fact Store:** Relational ground truth (SQLite or PostgreSQL) storing atomic, versioned key-value facts, user preferences, and entity constraints.
  - **Tier 3: Semantic Vector Store:** Dense HNSW vector index (Qdrant or Chroma) with payload-level filtering (`user_id`, `is_active`, dates).
- **The 4 Operational Stitches:**
  - **Stitch 1: Triage & Fact Extractor:** Fast extraction of atomic facts, entities, and summaries from chat turns while filtering ephemeral chit-chat.
  - **Stitch 2: Cross-Referencing ID:** Unified UUID propagation across SQL relational metadata and vector payloads.
  - **Stitch 3: Conflict & Deduplication Resolver:** Automatic contradiction detection (e.g. *"Moved from Berlin to Tokyo"*) with semantic versioning and superseding.
  - **Stitch 4: Dynamic Context Synthesizer:** Compresses memories into concentrated, token-budgeted prompt injections (< 500 tokens).
- **Autonomous Consolidation ("REM Sleep"):** Background worker that compresses raw multi-turn session histories into long-term vector milestones and purges ephemeral working memory.
- **Fact Decay & Relevance Scoring:** Soft exponential decay with frequency-based reinforcement for long-term relevance.
- **Zero-Dependency Offline Mode:** Ships with deterministic local hashing embeddings and in-memory Qdrant/SQLite for 100% offline development.
- **Dual Delivery Interface:** Exposes both a **FastAPI REST API** and a native **Model Context Protocol (MCP)** server for IDEs (Antigravity, Cursor, Windsurf).

---

## 2. Directory Structure

```
memory/
├── pyproject.toml                     # Dependencies & package configuration
├── README.md                          # Architecture & usage guide
├── config.py                          # Global configuration (backends, API keys, thresholds)
├── engine.py                          # Unified MemoryManager (Facade API)
├── core/
│   ├── __init__.py
│   ├── models.py                      # Pydantic schemas (MemoryRecord, FactItem, Turn, ContextPackage)
│   ├── interfaces.py                  # Abstract Base Classes (BaseWorkingTier, BaseFactTier, BaseVectorTier)
│   └── exceptions.py                  # Custom error definitions
├── tiers/
│   ├── __init__.py
│   ├── working/                       # Tier 1: Working Memory
│   │   ├── __init__.py
│   │   ├── in_memory.py               # Local in-memory working buffer with WAL
│   │   └── redis_adapter.py           # Production Redis working state
│   ├── facts/                         # Tier 2: Structured Fact Store
│   │   ├── __init__.py
│   │   ├── sqlite_adapter.py          # Local SQLite structured fact store
│   │   └── postgres_adapter.py        # Production PostgreSQL fact store
│   └── semantic/                      # Tier 3: Semantic Vector Store
│       ├── __init__.py
│       ├── chroma_adapter.py          # Local Chroma vector store adapter
│       └── qdrant_adapter.py          # Production Qdrant vector engine
├── stitches/
│   ├── __init__.py
│   ├── extractor.py                   # Stitch 1: LLM extraction of atomic facts and tags
│   ├── conflict_resolver.py           # Stitch 3: Deduplication and contradiction resolution
│   ├── consolidation.py               # Phase 4: Autonomous Consolidation loop ("REM Sleep")
│   └── synthesizer.py                 # Stitch 4: Context synthesizer for prompt injection (< 500 tokens)
├── embeddings/
│   ├── __init__.py
│   └── embedder.py                    # Unified embedding client (Local Hash / Remote OpenAI)
├── server/
│   ├── __init__.py
│   ├── app.py                         # FastAPI REST application
│   └── mcp_server.py                  # Model Context Protocol (MCP) server for IDEs
└── tests/
    ├── __init__.py
    ├── test_engine.py                 # End-to-end integration and verification tests
    ├── test_stitches.py               # Unit tests for extraction & conflict resolution
    └── test_tiers.py                  # Storage adapter verification tests
```

---

## 3. Quickstart & Usage

### 3.1 Python Facade API (`engine.py`)

```python
from engine import MemoryEngine

engine = MemoryEngine()

# 1. Remember interaction (auto-extracts facts, updates Tier 1, 2, 3)
engine.remember(
    user_id="alice",
    text="I only write Go code now, dropped Rust.",
    session_id="session_01",
)

# 2. Recall concentrated context (< 500 tokens) for system prompt injection
package = engine.recall(
    user_id="alice",
    query="What language should we use for the new service?",
    session_id="session_01",
)

print(package.formatted_prompt)
# Output:
# <agent_memory_context>
# ### Active Profile & Facts
# - preferred_language: Go [preference]
# ### Retrieved Archival Context
# - I only write Go code now, dropped Rust.
# </agent_memory_context>

# 3. Consolidate session when completed (REM Sleep cycle)
engine.consolidate(user_id="alice", session_id="session_01")
```

---

### 3.2 FastAPI REST Server

Run the REST API:
```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:
- `POST /api/v1/remember` - Store turn, extract facts, resolve contradictions
- `POST /api/v1/recall` - Retrieve synthesized prompt context
- `GET /api/v1/facts/{user_id}` - Get ground-truth active facts
- `POST /api/v1/consolidate` - Trigger background session consolidation
- `GET /health` - Health and storage backend status

---

### 3.3 Model Context Protocol (MCP) Server for IDEs

Configure in your IDE's MCP settings (e.g. `antigravity_ide.json` or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "pheonix-memory": {
      "command": "python",
      "args": ["d:/pheonix/memory/server/mcp_server.py"]
    }
  }
}
```

Exposed IDE Tools:
- `recall_memory(user_id, query, session_id)`
- `save_memory(user_id, text, session_id)`
- `list_user_facts(user_id)`
- `consolidate_session(user_id, session_id)`

---

## 4. Test Suite

Run the full verification suite using pytest:

```bash
pytest
```

Verification Checklist Tested:
1. **Attribution & Identity:** Recalls user profile, stack, and constraints across sessions.
2. **Contradiction Resolution:** *"Moved from Berlin to Tokyo"* marks Berlin superseded and stores Tokyo v2.
3. **Token Budget Boundary:** Synthesized context stays strictly within budget (< 500 tokens).
4. **Offline Capability:** Fully functional offline using SQLite, Qdrant in-memory, and local embeddings.
