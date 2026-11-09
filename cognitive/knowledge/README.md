# Layer 3: Knowledge Engine

The Knowledge Engine provides unified RAG pipelines, Global Hybrid Search (BM25 lexical + dense vector embeddings), and GraphRAG knowledge graph traversal across multi-source knowledge corpora.

---

## 1. Architecture & Capabilities

- **Hybrid Search Engine:** Combines Meilisearch / BM25 lexical retrieval and dense vector embeddings (Qdrant / Chroma).
- **3-Source Reciprocal Rank Fusion (RRF):**
  Fuses ranked candidate lists from lexical search, vector similarity, and knowledge graph traversal:
  $$\text{score}(d) = w_{\text{lex}} \cdot \frac{1}{k + \text{rank}_{\text{lex}}} + w_{\text{vec}} \cdot \frac{1}{k + \text{rank}_{\text{vec}}} + w_{\text{graph}} \cdot \frac{1}{k + \text{rank}_{\text{graph}}}$$
- **GraphRAG Traversal (FalkorDB Adapter):**
  Enables multi-hop entity-relationship traversals (e.g. corporate hierarchies, acquisition chains, dependency graphs) via Cypher.

---

## 2. FalkorDB Adapter (GraphRAG)

- **Repo:** [https://github.com/FalkorDB/FalkorDB](https://github.com/FalkorDB/FalkorDB)
- **License:** SSPL-1.0
- **Why Chosen:** Purpose-built in-memory graph database designed specifically for GraphRAG workloads, leveraging Cypher and Redis protocol for ultra-fast multi-hop traversals.
- **Configuration:**
  - `FALKORDB_HOST`: Host of FalkorDB server (default: `localhost`, use `:memory:` for hermetic in-memory execution).
  - `FALKORDB_PORT`: Port (default: `6380`, avoiding Redis on 6379).
  - Docker Compose: service `falkordb` using image `falkordb/falkordb:latest` on port `6380:6379`.

### Usage Example

```python
from knowledge.graph.falkordb_adapter import FalkorDBAdapter

adapter = FalkorDBAdapter(host="localhost", port=6380)

# Build entity relationships
adapter.add_relationship(source="Bob", relation="MANAGES", target="Alice")
adapter.add_relationship(source="Bob", relation="WORKS_AT", target="Megacorp")
adapter.add_relationship(source="Megacorp", relation="ACQUIRED", target="StartupAI")

# Multi-hop query: "What companies does Alice's manager's company acquire?"
acquisitions = adapter.query_manager_company_acquisitions(employee_name="Alice")
print(acquisitions)  # ['StartupAI']
```

---

## 3. Abstention Logic & Hallucination Prevention (Feature 3.35)

Located in `cognitive/knowledge/abstention/`:
- **Principled Refusal vs Hallucination:** When evidence retrieved from search or RAG is insufficient, irrelevant, or contradictory, the engine abstains with a verified refusal rather than generating ungrounded facts.
- **Evidence Grounding Evaluator (`evaluator.py`):** Calculates composite grounding confidence based on relevance, query keyword coverage, and cross-passage contradiction penalties.
- **Abstention Engine (`engine.py`):** Wraps generation pipelines; gates LLM execution behind verification thresholds (`ANSWER`, `PARTIAL`, `ABSTAIN`).

---

## 4. Source Quality & Authority Scorer (Feature 3.43)

Located in `cognitive/knowledge/quality/`:
- **Multi-Factor Source Evaluation:** Blends domain authority heuristics, content depth, code/spec signals, and temporal freshness into a single composite trustworthiness score ($0.0 - 1.0$).
- **Anti-Spam & Clickbait Penalties:** Penalizes low-value SEO clickbait, affiliate spam, and deceptive marketing claims to prevent grounding contamination.
- **Pluggable LLM-as-Judge Hook:** Allows runtime LLM factual rigor evaluation to refine heuristic content scores.
- **Tier Classification:** Categorizes sources into `TIER_1_AUTHORITATIVE`, `TIER_2_RELIABLE`, `TIER_3_UNVERIFIED`, and `TIER_4_LOW_QUALITY`.

---

## 5. Copyright & License Provenance Tagger (Features 3.45, 3.46)

Located in `cognitive/knowledge/provenance/`:
- **SPDX & License Recognition:** Analyzes ingestion text for SPDX tags (`SPDX-License-Identifier`), permissive licenses (MIT, Apache-2.0, BSD), and Creative Commons constraints.
- **Copyleft & Viral Clause Detection:** Identifies GPL/AGPL clauses and flags requirements for source disclosure to prevent licensing contamination.
- **Proprietary & Trade Secret Protection:** Flags confidential headers (`CONFIDENTIAL`, `PROPRIETARY AND CONFIDENTIAL`, `TRADE SECRET`) and restricts commercial or model training use.
- **Copyright Notice Extraction:** Captures structured copyright notices with publication years and copyright holders.

---

## 6. Point-in-Time Knowledge Snapshots (Feature 3.24)

Located in `cognitive/knowledge/snapshots/`:
- **Immutable Knowledge Checkpoints:** Captures point-in-time snapshots of notes, documents, chunk collections, and graph relationships.
- **Structural Snapshot Diffing (`diff_snapshots`):** Compares versions to track additions, deletions, and modifications of knowledge items and relational triples.
- **Point-in-Time Querying (`query_point_in_time`):** Enables historical retrieval strictly scoped to knowledge state as of a specific checkpoint or audit tag.

