"""Unit tests for DataLineageTracker (Task 15.6)."""

import pytest
from platform.data.lineage.tracker import (
    DataLineageTracker,
    NodeType,
    RelationType,
)


@pytest.fixture
def tracker():
    return DataLineageTracker()


def test_record_and_trace_upstream_source(tracker: DataLineageTracker):
    """Can trace derived data item to its original root source."""
    tracker.record_source(
        source_id="src_sec_edgar",
        name="SEC EDGAR 10-K API",
        metadata={"url": "https://data.sec.gov", "compliance": "public"},
    )
    tracker.record_data_item(
        item_id="raw_10k_apple",
        name="AAPL 2025 10-K Document",
        source_id="src_sec_edgar",
    )
    tracker.record_derivation(
        derived_item_id="clean_ebitda_metric",
        name="Apple 2025 EBITDA Table",
        parent_item_ids=["raw_10k_apple"],
        transformation_name="parse_xbrl_tables",
    )

    upstream = tracker.get_upstream_sources("clean_ebitda_metric")
    assert len(upstream) == 1
    assert upstream[0].node_id == "src_sec_edgar"
    assert upstream[0].name == "SEC EDGAR 10-K API"


def test_record_and_trace_downstream_consumers(tracker: DataLineageTracker):
    """Can trace data item forward to all consumers that ingested it or its derivatives."""
    tracker.record_source("src_sensor_iot", "IoT Temperature Sensor A1")
    tracker.record_data_item("temp_telemetry_batch_1", "Batch 1 Telemetry", source_id="src_sensor_iot")

    # Direct consumer of raw telemetry
    tracker.record_consumption(
        consumer_id="anomaly_detector_agent",
        consumer_name="Realtime Anomaly Detection",
        item_id="temp_telemetry_batch_1",
        action="evaluate_spikes",
    )

    # Derivation: aggregated hourly stats
    tracker.record_derivation(
        derived_item_id="hourly_avg_temp",
        name="Hourly Aggregated Temperature",
        parent_item_ids=["temp_telemetry_batch_1"],
        transformation_name="hourly_mean_resample",
    )

    # Consumer of derived stats
    tracker.record_consumption(
        consumer_id="daily_dashboard_ui",
        consumer_name="Executive Environmental Dashboard",
        item_id="hourly_avg_temp",
        action="render_widget",
    )

    # Downstream of raw batch should find BOTH direct and indirect consumers
    consumers = tracker.get_downstream_consumers("temp_telemetry_batch_1")
    consumer_ids = {c.node_id for c in consumers}
    assert consumer_ids == {"anomaly_detector_agent", "daily_dashboard_ui"}


def test_trace_full_lineage_metadata(tracker: DataLineageTracker):
    """Test comprehensive lineage dictionary export."""
    tracker.record_source("src_db", "Production Postgres")
    tracker.record_data_item("users_table", "Users Table", source_id="src_db")
    tracker.record_consumption("export_csv_job", "CSV Exporter", "users_table")

    lineage = tracker.trace_full_lineage("users_table")
    assert lineage["item_id"] == "users_table"
    assert lineage["total_sources"] == 1
    assert lineage["total_consumers"] == 1
    assert lineage["sources"][0]["node_id"] == "src_db"
    assert lineage["consumers"][0]["node_id"] == "export_csv_job"

