"""Unit tests for Federated Learning (Task 19.6)."""

import pytest
from surface.federation.learning.federated_learning import (
    FederatedLearningManager,
    TenantLearningNode,
)


@pytest.fixture
def fed_manager():
    return FederatedLearningManager()


def test_tenant_training_data_stays_local_only_weight_updates_shared(fed_manager: FederatedLearningManager):
    """Acceptance test: Tenant A's training data stays local; only weight updates shared."""
    # Register Tenant A (e.g. Hospital A)
    tenant_a = fed_manager.register_tenant("tenant_hospital_a")

    # Ingest confidential local patient records onto Tenant A node
    tenant_a.ingest_local_data([
        {"patient_id": "P_1001", "diagnosis": "Hypertension Stage 2", "bp_sys": 145},
        {"patient_id": "P_1002", "diagnosis": "Type 2 Diabetes", "a1c": 7.4},
        {"patient_id": "P_1003", "diagnosis": "Coronary Artery Disease", "cholesterol": 230},
    ])
    assert len(tenant_a._private_dataset) == 3

    # Tenant A trains locally on-premise
    import copy
    initial_weights = copy.deepcopy(fed_manager.global_weights)
    delta_a = tenant_a.train_local_epoch(base_weights=initial_weights, round_number=1)

    # Security check: verify delta contains ONLY numeric weight deltas, absolutely zero patient records
    assert delta_a.tenant_id == "tenant_hospital_a"
    assert delta_a.num_samples == 3
    for layer, deltas in delta_a.weight_deltas.items():
        assert all(isinstance(val, float) for val in deltas)
        assert len(deltas) == len(initial_weights[layer])

    # Ensure patient details never leaked into delta attributes or metadata
    delta_dict = delta_a.__dict__
    assert "P_1001" not in str(delta_dict)
    assert "Hypertension" not in str(delta_dict)

    # Register Tenant B (Clinic B) with 7 samples
    tenant_b = fed_manager.register_tenant("tenant_clinic_b")
    tenant_b.ingest_local_data([{"sample_id": i} for i in range(7)])
    delta_b = tenant_b.train_local_epoch(base_weights=initial_weights, round_number=1)

    # Submit both deltas to core aggregator
    fed_manager.submit_weight_update(delta_a)
    fed_manager.submit_weight_update(delta_b)

    # Core performs Federated Averaging (FedAvg)
    new_global_weights = fed_manager.aggregate_round()

    assert fed_manager.current_round == 2
    # Weights have mathematically updated
    assert new_global_weights["layer_embedding"] != initial_weights["layer_embedding"]
    assert len(new_global_weights["layer_embedding"]) == len(initial_weights["layer_embedding"])
