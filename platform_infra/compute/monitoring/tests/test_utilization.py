"""Tests for L16 utilization monitoring and autoscaling signals."""

from platform_infra.compute.monitoring.utilization import (
    AutoscalingAction,
    NodeUtilizationSample,
    UtilizationMonitor,
)


def test_query_all_nodes_and_autoscale_recommendations():
    mon = UtilizationMonitor(scale_up_gpu_pct=80.0, scale_down_gpu_pct=20.0, min_replicas=1, max_replicas=8)
    mon.record_sample(
        NodeUtilizationSample(
            node_id="gpu-node-1",
            gpu_util_pct=88.5,
            gpu_memory_used_gb=70.0,
            gpu_memory_total_gb=80.0,
            cpu_util_pct=45.0,
            ram_used_gb=120.0,
            ram_total_gb=256.0,
            active_requests=42,
        )
    )
    mon.record_sample(
        NodeUtilizationSample(
            node_id="gpu-node-2",
            gpu_util_pct=84.0,
            gpu_memory_used_gb=65.0,
            gpu_memory_total_gb=80.0,
            cpu_util_pct=40.0,
            ram_used_gb=110.0,
            ram_total_gb=256.0,
            active_requests=38,
        )
    )

    gpu_map = mon.get_all_gpu_utilization()
    assert gpu_map == {"gpu-node-1": 88.5, "gpu-node-2": 84.0}
    summary = mon.query_cluster_summary()
    assert summary.node_count == 2
    assert summary.total_active_requests == 80
    rec = mon.recommend_autoscaling(current_replicas=2)
    assert rec.action == AutoscalingAction.SCALE_UP
    assert rec.recommended_replicas >= 3

    # Cool down -> scale down
    mon.record_sample(NodeUtilizationSample("gpu-node-1", 10.0, 12.0, 80.0, 10.0, 32.0, 256.0, 1))
    mon.record_sample(NodeUtilizationSample("gpu-node-2", 12.0, 12.0, 80.0, 10.0, 32.0, 256.0, 2))
    rec_down = mon.recommend_autoscaling(current_replicas=3)
    assert rec_down.action == AutoscalingAction.SCALE_DOWN
    assert rec_down.recommended_replicas == 2

