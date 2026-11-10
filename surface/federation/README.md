# Central Intelligence — Layer 19: Specialization & Federation

Layer 19 powers domain-specialized cognitive brains, privacy-preserving cross-tenant federated learning, and the **Federated Brain Sync Protocol (Crown Jewel 19.04, 19.12-19.16)**.

## Subsystems & Architecture

| Feature ID | Module | Implementation | Description |
|---|---|---|---|
| **19.1** | `surface/federation/pm` | `HulyAdapter` | Unified workspace for project management and collaborative documentation with autonomous agent task creation. |
| **19.01-19.07** | `surface/federation/brain` | `SpecializedBrainFactory` | Domain-specialized cognitive brains (Legal, Dev, Healthcare) with curated corpora, personas, and retirement archival. |
| **19.04, 19.12-19.16** | `surface/federation/sync` | `FederatedBrainSync` 🚩 **CROWN JEWEL** | Cryptographic protocol enabling specialized brains to exchange verified, signed, and encrypted sub-task outputs with consent gates. |
| **19.22, 19.23** | `surface/federation/registry` | `SkillPackRegistry` | Manifest validation and sandboxing for community/domain skill packs with revocation controls. |
| **19.20, 19.31-19.34** | `surface/federation/memory` | `CrossAppMemorySharing` | Cross-app memory sharing respecting strict data walls (universal user preferences shared, private content sequestered). |
| **19.29, 19.30** | `surface/federation/learning` | `FederatedLearningManager` | On-premise local training where sensitive tenant data never leaves the tenant boundary; only aggregated weight deltas (FedAvg) are shared. |
| **19.35** | `surface/federation/review` | `SharingGate` | Review-before-wider-sharing gate enforcing governance checks before assets are promoted from Private → Team → Org. |

## Testing

```bash
pytest surface/federation/ -v
```
