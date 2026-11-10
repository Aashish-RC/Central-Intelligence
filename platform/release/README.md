# Central Intelligence — Layer 17: Release & Lifecycle

Layer 17 governs application deployment, zero-downtime CI rollouts, feature experimentation, database migrations, backward compatibility guards, and automated quality gates.

## Subsystems & Architecture

| Feature ID | Module | Implementation | Description |
|---|---|---|---|
| **17.1** | `platform/release/paas` | `CoolifyAdapter` | Self-hosted PaaS integration for git-push container deployments, automated SSL, and environment rollbacks. |
| **17.2** | `platform/release/ci` | `KamalAdapter` | Zero-downtime container proxy swap deployments directly from CI pipelines. |
| **17.3** | `platform/release/flags` | `GrowthBookAdapter` | Feature toggles, canary percentage rollouts (e.g. 5% canary), and deterministic user experimentation. |
| **17.4** | `platform/release/db` | `BytebaseAdapter` | Database CI/CD with mandatory review gates, DDL migration execution, and reversible rollbacks. |
| **17.08, 17.13-17.15** | `platform/release/migration` | `MigrationRollbackGuard` | Dry-run compatibility validator blocking schema migrations that would break active, in-flight user sessions. |
| **17.12** | `platform/release/gates` | `PlatformReleaseGate` | Production release gates wired to L11 evaluation benchmarks blocking releases with quality regressions. |

## Testing

```bash
pytest platform/release/ -v
```

