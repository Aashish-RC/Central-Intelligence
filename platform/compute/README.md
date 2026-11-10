# Central Intelligence — Layer 16: Compute & Model Serving

Layer 16 manages compute dispatching, energy and carbon routing, model cataloging, provider health monitoring, zero-downtime hot-swapping, and safe physical actuation.

## Subsystems & Architecture

| Feature ID | Module | Implementation | Description |
|---|---|---|---|
| **16.07, 16.17** | `platform/compute/dispatcher` | `HardwareTierDispatcher` | Evaluates local GPU/VRAM/battery to route inference to local Ollama (if capable) or cloud vLLM/APIs. |
| **16.28** | `platform/compute/energy` | `CarbonEnergyRouter` | Tracks energy expenditure (Joules/request), routes to renewable regions, and defers heavy batch tasks to off-peak grid hours. |
| **16.22-16.26** | `platform/compute/registry` | `ModelCatalog` | Registry of model variants with capabilities, limits, pricing per million tokens, and live operational health. |
| **16.26** | `platform/compute/health` | `ProviderHealthTracker` | Circuit-breaker tracking provider availability, consecutive failures, and HTTP 429 rate limit backoffs. |
| **16.05** | `platform/compute/lifecycle` | `ModelHotSwapManager` | Zero-downtime model hot-swapping with graceful in-flight request draining and atomic cutover. |
| **16.29, 16.30** | `platform/compute/actuation` | `DeviceActuationController` | Physical IoT / hardware device actuation with confirmation gates, rate limits, and state rollback. |

## Testing

```bash
pytest platform/compute/ -v
```
