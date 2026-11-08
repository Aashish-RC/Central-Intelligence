# Aevum Architecture: 20 Cognitive Pillars

Aevum provides a centralized "Brain Factory" that provisions, configures, and operates customized AI Brains across multiple client products.

```
+-----------------------------------------------------------------------------------+
|                                AEVUM AI CORE                                      |
+-----------------------------------------------------------------------------------+
| Tier 0: Perception                                                                |
|   1. Inputs                                                                       |
+-----------------------------------------------------------------------------------+
| Tier 1: Cognition                                                                 |
|   2. Model Gateway | 3. Memory | 4. RAG | 5. NLU | 6. Reasoning                   |
+-----------------------------------------------------------------------------------+
| Tier 2: Action                                                                    |
|   7. Agents | 8. Orchestration | 9. Execution | 10. Workflow                      |
+-----------------------------------------------------------------------------------+
| Tier 3: Output                                                                    |
|   11. Output/Generation                                                           |
+-----------------------------------------------------------------------------------+
| Tier 4: Personalization                                                           |
|   12. Recommender | 13. Identity/Profile                                          |
+-----------------------------------------------------------------------------------+
| Tier 5: Governance                                                                |
|   14. Guardrails | 15. Policy                                                     |
+-----------------------------------------------------------------------------------+
| Tier 6: Operations                                                                |
|   16. State/Session | 17. Observability | 18. Evaluation | 19. Learning | 20. Versioning|
+-----------------------------------------------------------------------------------+
```

## Wave A Build Order

Wave A builds the foundational pillars:
1. **Pillar #13 (Identity)**: Authentication, Session Management, OAuth Vault, SSO, Consent Ledger, Audit Log.
2. **Pillar #1 (Inputs)**: Multimodal data ingestion, OAuth integration for user cloud storage (e.g. Google Drive, OneDrive).
3. **Pillar #2 (Model Gateway)**: Provider routing, fallbacks, streaming inference.
4. **Pillar #16 (State/Session)**: Conversational and execution state.
5. **Pillar #17 (Observability)**: Metrics, distributed tracing, and logging.

