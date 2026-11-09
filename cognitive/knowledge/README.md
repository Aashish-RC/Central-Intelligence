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

