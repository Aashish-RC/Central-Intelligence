"""Unit tests for AutoMQAdapter (Task 15.3)."""

import pytest
from platform.data.messaging.automq_adapter import (
    AutoMQAdapter,
    AutoMQConfig,
    EventRecord,
    EventSchema,
)


@pytest.fixture
def automq():
    config = AutoMQConfig(use_mock=True)
    adapter = AutoMQAdapter(config=config)

    # Register sample event schema
    adapter.register_schema(
        EventSchema(
            name="agent.task.created",
            version=1,
            required_fields=["task_id", "user_id", "model"],
        )
    )
    return adapter


def test_schema_validation_and_publishing(automq: AutoMQAdapter):
    """Test valid event publishes and invalid payload raises ValueError."""
    valid_payload = {
        "task_id": "tsk_001",
        "user_id": "usr_99",
        "model": "claude-3-7-sonnet",
        "prompt": "Optimize SQL queries",
    }
    event = automq.publish(
        topic="agent.tasks",
        payload=valid_payload,
        schema_name="agent.task.created",
        schema_version=1,
        key="usr_99",
    )
    assert event.event_id.startswith("evt_")
    assert event.offset == 0
    assert event.topic == "agent.tasks"

    # Invalid payload (missing user_id)
    invalid_payload = {
        "task_id": "tsk_002",
        "model": "claude-3-7-sonnet",
    }
    with pytest.raises(ValueError, match="Missing required field: 'user_id'"):
        automq.publish(
            topic="agent.tasks",
            payload=invalid_payload,
            schema_name="agent.task.created",
            schema_version=1,
        )


def test_ordered_consumption_and_commits(automq: AutoMQAdapter):
    """Test ordered stream consumption across offsets."""
    topic = "user.actions"
    for i in range(5):
        automq.publish(
            topic=topic,
            payload={"action": f"click_{i}"},
            schema_name="generic",
            schema_version=1,
        )

    # First batch of 2
    batch1 = automq.consume(topic=topic, consumer_group="group_a", batch_size=2)
    assert len(batch1) == 2
    assert [e.offset for e in batch1] == [0, 1]
    automq.commit(topic, "group_a", offset=2)

    # Second batch of 2
    batch2 = automq.consume(topic=topic, consumer_group="group_a", batch_size=2)
    assert len(batch2) == 2
    assert [e.offset for e in batch2] == [2, 3]
    automq.commit(topic, "group_a", offset=4)

    # Last batch of 2 (only 1 remaining)
    batch3 = automq.consume(topic=topic, consumer_group="group_a", batch_size=2)
    assert len(batch3) == 1
    assert batch3[0].offset == 4


def test_dead_letter_queue_handling_and_replay(automq: AutoMQAdapter):
    """Test that failed event executions are routed to DLQ and can be replayed."""
    topic = "payments.process"
    automq.publish(topic, {"amount": 100, "valid": True}, "payment", 1)
    automq.publish(topic, {"amount": -50, "valid": False}, "payment", 1)  # Will fail
    automq.publish(topic, {"amount": 250, "valid": True}, "payment", 1)

    processed = []

    def payment_handler(event: EventRecord):
        if not event.payload.get("valid"):
            raise ValueError("Invalid negative payment amount")
        processed.append(event.payload["amount"])

    succeeded, failed = automq.process_and_commit(
        topic=topic,
        consumer_group="billing_worker",
        handler=payment_handler,
    )

    assert succeeded == 2
    assert failed == 1
    assert processed == [100, 250]

    # Inspect DLQ
    dlq_records = automq.get_dlq_records(topic)
    assert len(dlq_records) == 1
    assert "Invalid negative payment amount" in dlq_records[0].error_message
    assert dlq_records[0].original_event.payload["amount"] == -50

    # Fix error on replay:
    def permissive_handler(event: EventRecord):
        processed.append(abs(event.payload["amount"]))

    replayed, still_failing = automq.replay_dlq(topic, permissive_handler)
    assert replayed == 1
    assert still_failing == 0
    assert processed == [100, 250, 50]
    assert len(automq.get_dlq_records(topic)) == 0

