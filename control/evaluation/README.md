# Layer 11: Evaluation & Quality

Continuous evaluation, hallucination detection, regression testing, drift analysis, multi-agent simulation, and multi-pillar quality scoring.

---

## 1. Core Modules

### `control.evaluation.phoenix` (`phoenix_adapter.py`)
- **Arize Phoenix Integration (11.01, 11.08, 11.10):**
  - OpenTelemetry-compatible multi-step agent trace capture.
  - Factual grounding and hallucination detection against retrieved context.
  - Wasserstein and cosine embedding distribution drift detection across interactions.

### `control.evaluation.langwatch` (`langwatch_adapter.py`)
- **LangWatch Integration (11.04):**
  - Multi-agent scenario simulation testing.
  - Adversarial conversation probing and automated regression evaluation.

### `control.evaluation.accuracy` (Crown Jewel: Accuracy Score Evaluator)
- **3-Pillar Composite Accuracy ($S_{composite}$ - 11.14):**
  $$S_{composite} = w_1 S_{feedback} + w_2 S_{web} + w_3 S_{consensus}$$
  - $S_{feedback}$: Aggregated explicit and implicit user feedback (thumbs up/down, corrections).
  - $S_{web}$: Real-time web verification of atomic claims decomposed by L4.
  - $S_{consensus}$: Multi-model cross-agreement verification from L4 MoA fusion.
- **Action Thresholds (11.16):**
  - $S \ge 0.80$: Deliver directly.
  - $0.50 \le S < 0.80$: Flag low confidence, suggest verification.
  - $S < 0.50$: **Trigger Second Opinion (DEF-03 unblocked)** / human clarification.
- **Calibration (11.15):** Stated confidence vs actual observed correctness tracking.
- **Transparency (11.17):** Configurable score visibility for client surfaces.

### `control.evaluation.datasets` (`dataset_store.py`, `custom_scorer.py`, `golden_suites.py`)
- Domain-specific evaluation datasets, custom programmatic scorers, and golden CI regression suites.

### `control.evaluation.simulation` (`scenario_runner.py`)
- Scenario runner executing multi-turn user/agent dialogs with simulated adversarial actors.

### `control.evaluation.e2e` (`test_runner.py`)
- Cross-layer integration pipeline runner validating L1 through L8 continuity.

### `control.evaluation.online`
- Automated LLM judge scoring, human review sampling, failure clustering, bias/fairness measurement, and satisfaction tracking.

### `control.evaluation.experiments`
- A/B testing harnesses for models, prompts, and routing policies with statistical significance checks and automated release quality gates.

### `control.evaluation.sandbox` (`tenant_sandbox.py`)
- Tenant-level simulation mode preventing external mutations while exercising complete reasoning and tool planning.

---

## 2. Docker Service

Arize Phoenix is registered in `docker-compose.yml`:
- Service: `phoenix`
- Image: `arizephoenix/phoenix:latest`
- Port: `6006`

---

## 3. Testing

Run L11 tests with:
```bash
python -m pytest control/evaluation/tests/ -v
```

