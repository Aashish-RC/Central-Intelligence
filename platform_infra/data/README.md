# Central Intelligence — Layer 15: Data & Messaging

Layer 15 provides unified data persistence, high-speed caching, event streaming, multi-device synchronization, per-app sandboxing, and full end-to-end data provenance.

## Subsystems & Architecture

| Feature ID | Module | Implementation | Description |
|---|---|---|---|
| **15.1** | `platform_infra/data/supabase` | `SupabaseAdapter` | Postgres + pgvector + Apache AGE + Row-Level Security (RLS). Replaces standalone vector/graph stores. |
| **15.2** | `platform_infra/data/cache` | `DragonflyAdapter` | 25× faster drop-in Redis replacement for multi-threaded in-memory caching and real-time Pub/Sub. |
| **15.3** | `platform_infra/data/messaging` | `AutoMQAdapter` | S3-native serverless Kafka streaming with ordered topics, versioned schemas, and Dead-Letter Queues (DLQ). |
| **15.38, 15.39** | `platform_infra/data/sync` | `CrossDeviceReconciler` | CRDT-based multi-device synchronization engine reconciling conversations across phone, desktop, and web without data loss. |
| **15.34, 15.35** | `platform_infra/data/isolation` | `AppSandbox` | Virtual schema isolation per application with granular, time-bounded cross-app authorization grants and audit logging. |
| **15.36** | `platform_infra/data/lineage` | `DataLineageTracker` | Directed Acyclic Graph (DAG) recording data provenance from original sources to downstream consumers. |

## Testing

```bash
pytest platform_infra/data/ -v
```

