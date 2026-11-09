# Architecture Evaluation: Hatchet vs Temporal for Central-Intelligence

**Document Version:** 1.0.0  
**Target Systems:** Layer 8 (Orchestration & Workflow Engine), Layer 5 (Action Worker Fleet)  
**Status:** Evaluated & Documented (Phase 5, P2)

---

## 1. Executive Summary

Central-Intelligence requires durable, fault-tolerant workflow execution for long-horizon agent tasks, multi-agent collaboration, and human-in-the-loop escalations. 

We evaluated **Temporal** (currently integrated via `temporal_adapter.py` and `temporalBridge.ts` under Feature 8.31) versus **Hatchet** (an open-source distributed task queue engine built on Go and PostgreSQL), alongside traditional task queues (Celery/BullMQ).

### Architectural Recommendation

1. **Retain Temporal as Primary Durable Orchestrator (L8):**  
   Temporal's deterministic event-sourcing replay model is unmatched for multi-hour and multi-day long-horizon agent workflows, speculative rollbacks, and complex nested child workflows where execution code is written as normal code that resumes transparently across pod restarts or network interruptions.

2. **Benchmark Hatchet for High-Throughput I/O & Sandbox Queues (L5):**  
   Hatchet offers simpler operational overhead (single Postgres instance vs Temporal cluster) and native per-key concurrency limits (e.g. max 5 concurrent browser sessions per tenant). Hatchet is an ideal candidate for high-frequency, short-lived ephemeral worker dispatch (sandboxes, web scraping, scraping fan-outs) where full event-sourced replay history is unnecessary.

---

## 2. Technical Comparison Matrix

| Architectural Dimension | Temporal | Hatchet | Traditional (Celery / BullMQ) |
| :--- | :--- | :--- | :--- |
| **Execution Model** | Deterministic Event-Sourced Replay | Postgres-backed Directed Task Graph | Ephemeral Message Queue + Redis/Broker |
| **Persistence Engine** | Cassandra / PostgreSQL / MySQL | Single PostgreSQL (via pg_notify & triggers) | Redis / RabbitMQ |
| **State Recovery** | Replays workflow code deterministically to reconstruct state | Step-level status checkpoints in relational database | Unacked messages or manual DB state tracking |
| **Long-Horizon Timers** | Native durable timers (days, months) with zero idle compute | Database scheduled jobs / polling intervals | Redis TTL / Beat scheduler |
| **Concurrency Controls** | Custom signal/query patterns or mutex workflows | Native per-key concurrency limits & FIFO priority queues | Redis locks or token bucket |
| **Human-in-the-Loop** | Native Signals, Queries, and external workflow updates | Webhook events & task resumption | Custom polling API |
| **Operational Complexity** | High (Server, UI, Database, Web, Admin Tools) | Low-Medium (Single Go binary + PostgreSQL) | Low (Redis / Broker + Workers) |
| **SDK Support** | Python, TypeScript, Go, Java, .NET | Python, TypeScript, Go | Python (Celery), TS (BullMQ) |
| **Licensing** | MIT | MIT | BSD-3-Clause / MIT |

---

## 3. In-Depth Analysis

### 3.1 Event-Sourcing vs Database-Backed Task Graphs
- **Temporal's Advantage:** Temporal treats the entire workflow execution function as durable. If an agent script crashes on step 4 of 10, Temporal starts a new worker, replays steps 1-3 using recorded activity results without re-executing external calls, and resumes step 4 seamlessly. This enables natural code structures (`while`, `try...catch`, `await sleep(86400)`).
- **Hatchet's Advantage:** Hatchet persists step graphs in PostgreSQL. It does not require deterministic replay constraints (e.g. no global state, no random numbers, no unmocked time calls in workflow code). Developers write standard async functions as DAG steps.

### 3.2 Concurrency and Tenant Sandboxing
- In Layer 5 (Action & Sandboxes), agents invoke external tools with strict rate limits (e.g. 5 concurrent calls per user key). Hatchet provides built-in `concurrency: { key: "user_id", limit: 5 }` out of the box at the engine level. In Temporal, implementing per-user concurrency requires dynamic activity rate limiters or actor-style orchestrator workflows.

### 3.3 Infrastructure Footprint & DevOps
- **Temporal:** Running Temporal in local dev requires the `temporalio/auto-setup` Docker image, Elasticsearch/OpenSearch for advanced visibility, and separate frontend/history/matching services.
- **Hatchet:** Runs as a single lightweight binary alongside our existing PostgreSQL service (`docker-compose.yml`), reducing development resource consumption.

---

## 4. Central-Intelligence Integration Roadmap

```
+-------------------------------------------------------------------------+
| Layer 8: Orchestration Core                                             |
|  - Workflow Builder & Temporal Durable Orchestration (8.31)             |
|  - Cognitive Routing Policy Engine (8.09 - 8.15)                        |
|  - Human Escalation Protocol (8.30)                                     |
|  - Paperclip Fleet Management & Budgets (8.18, 8.48)                    |
+-------------------------------------------------------------------------+
                                    |
                    Task Dispatch & Worker Execution
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 5: Action & Sandbox Fleet                                         |
|  - Heavy Durable DAGs: Handled via Temporal Adapter                     |
|  - Ephemeral Fan-Out / I/O Workers: Target for Hatchet Queue Connector  |
|  - Per-Agent Sandboxes & Memory Isolation (5.38)                        |
|  - Curated Tool Registry & Rate Limiting (5.08)                         |
+-------------------------------------------------------------------------+
```

### Next Steps:
1. Continue utilizing the implemented `temporal_adapter.py` and `temporalBridge.ts` as the standard durable orchestration foundation.
2. In subsequent scalability phases, introduce an optional `HatchetQueueAdapter` in `control/orchestration/workflow_builder/runtime/` as an alternative backend for lightweight, single-database installations.
