# Layer 9: Context Engineering

Context Engineering provides multi-source context synthesis, strict per-tier token budgets, compaction algorithms, and tamper-resistant prompt injection defense.

---

## 1. Core Modules

### `control.context.assembly` (`context_assembler.py`)
- **Multi-Source Synthesis (9.01):** Integrates memory from L2, semantic search results from L3, active tool schemas from L5, and system directives into a unified prompt payload.
- **Token Allocation (9.02):** Enforces hard limits per category (system, memory, knowledge, tools, conversation) preventing memory or large search results from starving executable tool schemas.
- **Prioritization & Pruning (9.03):** When total tokens exceed the context window, drops lower-priority items (knowledge -> memory -> conversation) while strictly preserving system directives and tool schemas.
- **Conversation Compaction (9.04):** Compacts turns beyond the sliding window into bulleted gists using LlamaIndex-aligned history rolling algorithms.
- **Strategy Selector (9.05):** Dynamically chooses between Long Context pass-through and dense Retrieval-Augmented Compaction.

---

## 2. API Server

FastAPI service located at `control/context/server.py` exposing:
- `POST /v1/context/assemble`: Unified assembly endpoint for L4 Reasoning and external gateway callers.

---

## 3. Testing

Run L9 tests with:
```bash
python -m pytest control/context/tests/ -v
```
