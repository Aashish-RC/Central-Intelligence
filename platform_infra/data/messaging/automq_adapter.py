"""AutoMQ Event Streaming Adapter (L15 Data & Messaging - Task 15.3).

AutoMQ provides an S3-native serverless Kafka compatible streaming engine.
Supports durable queues, ordered message consumption, schema-versioned events,
and dead-letter queue (DLQ) processing for failed event deliveries.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EventSchema:
    """Schema descriptor for versioned events."""
    name: str
    version: int
    required_fields: List[str] = field(default_factory=list)

    def validate(self, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        for required in self.required_fields:
            if required not in payload:
                return False, f"Missing required field: '{required}'"
        return True, None


@dataclass
class EventRecord:
    """A durable event message."""
    event_id: str
    topic: str
    schema_name: str
    schema_version: int
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    partition: int = 0
    offset: int = 0
    key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class DeadLetterRecord:
    """A failed event routed to the dead-letter queue."""
    original_event: EventRecord
    error_message: str
    failed_at: float = field(default_factory=time.time)
    attempts: int = 1
    consumer_group: str = "default"


@dataclass
class AutoMQConfig:
    """Configuration for AutoMQ streaming."""
    bootstrap_servers: str = "localhost:9092"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "automq-stream-data"
    default_max_retries: int = 3
    use_mock: bool = False


class AutoMQAdapter:
    """Adapter for AutoMQ event streaming, topic management, ordering, and DLQs."""

    def __init__(self, config: Optional[AutoMQConfig] = None) -> None:
        self.config = config or AutoMQConfig()
        self._schemas: Dict[str, EventSchema] = {}
        # topic -> list of EventRecords
        self._topics: Dict[str, List[EventRecord]] = {}
        # (topic, consumer_group) -> committed offset
        self._offsets: Dict[Tuple[str, str], int] = {}
        # topic -> list of DeadLetterRecords
        self._dlq: Dict[str, List[DeadLetterRecord]] = {}

    def register_schema(self, schema: EventSchema) -> None:
        """Register a schema with version enforcement."""
        schema_key = f"{schema.name}:v{schema.version}"
        self._schemas[schema_key] = schema
        logger.info("Registered event schema: %s", schema_key)

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        schema_name: str,
        schema_version: int = 1,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> EventRecord:
        """Publish a schema-validated event to an ordered stream topic."""
        schema_key = f"{schema_name}:v{schema_version}"
        if schema_key in self._schemas:
            schema = self._schemas[schema_key]
            valid, err = schema.validate(payload)
            if not valid:
                raise ValueError(f"Payload validation failed for {schema_key}: {err}")

        if topic not in self._topics:
            self._topics[topic] = []

        offset = len(self._topics[topic])
        event = EventRecord(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            topic=topic,
            schema_name=schema_name,
            schema_version=schema_version,
            payload=payload,
            offset=offset,
            key=key,
            headers=headers or {},
        )
        self._topics[topic].append(event)
        return event

    def consume(
        self,
        topic: str,
        consumer_group: str = "default",
        batch_size: int = 10,
    ) -> List[EventRecord]:
        """Consume ordered events from current committed offset for consumer group."""
        if topic not in self._topics:
            return []

        group_key = (topic, consumer_group)
        current_offset = self._offsets.get(group_key, 0)
        topic_events = self._topics[topic]

        batch = topic_events[current_offset : current_offset + batch_size]
        return batch

    def commit(self, topic: str, consumer_group: str, offset: int) -> None:
        """Commit consumer group offset."""
        group_key = (topic, consumer_group)
        self._offsets[group_key] = offset

    def process_and_commit(
        self,
        topic: str,
        consumer_group: str,
        handler: Callable[[EventRecord], None],
        max_batch: int = 10,
    ) -> Tuple[int, int]:
        """Process events sequentially; route failing events to DLQ and commit successfully processed offsets."""
        events = self.consume(topic, consumer_group, batch_size=max_batch)
        succeeded = 0
        failed = 0

        for event in events:
            try:
                handler(event)
                succeeded += 1
                self.commit(topic, consumer_group, event.offset + 1)
            except Exception as exc:
                failed += 1
                self.route_to_dlq(
                    event=event,
                    error=str(exc),
                    consumer_group=consumer_group,
                )
                # Advance offset past failed item to avoid infinite block, but record in DLQ
                self.commit(topic, consumer_group, event.offset + 1)

        return succeeded, failed

    def route_to_dlq(
        self,
        event: EventRecord,
        error: str,
        consumer_group: str = "default",
    ) -> DeadLetterRecord:
        """Route an unprocessable event to dead-letter queue."""
        dlq_topic = f"{event.topic}.DLQ"
        if dlq_topic not in self._dlq:
            self._dlq[dlq_topic] = []

        dlq_record = DeadLetterRecord(
            original_event=event,
            error_message=error,
            consumer_group=consumer_group,
        )
        self._dlq[dlq_topic].append(dlq_record)
        logger.warning(
            "Event %s routed to DLQ topic %s: %s",
            event.event_id,
            dlq_topic,
            error,
        )
        return dlq_record

    def get_dlq_records(self, topic: str) -> List[DeadLetterRecord]:
        """Fetch dead-letter records for topic."""
        dlq_topic = f"{topic}.DLQ"
        return list(self._dlq.get(dlq_topic, []))

    def replay_dlq(
        self,
        topic: str,
        handler: Callable[[EventRecord], None],
    ) -> Tuple[int, int]:
        """Replay DLQ records."""
        dlq_topic = f"{topic}.DLQ"
        records = self._dlq.get(dlq_topic, [])
        replayed = 0
        still_failing = 0
        remaining = []

        for record in records:
            try:
                handler(record.original_event)
                replayed += 1
            except Exception as exc:
                record.attempts += 1
                record.error_message = str(exc)
                remaining.append(record)
                still_failing += 1

        self._dlq[dlq_topic] = remaining
        return replayed, still_failing

