"""Unit tests for KafkaEventProducer."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.pipelines.kafka_producer import (
    KafkaEventProducer,
    TOPIC_PATIENT_EVENTS,
    TOPIC_RECOMMENDATION_SERVED,
)


@pytest.mark.asyncio
async def test_send_noop_when_disabled():
    producer = KafkaEventProducer(enabled=False)
    await producer.start()
    await producer.send_patient_event("lab_appended", uuid.uuid4())
    assert producer._producer is None
    await producer.stop()


@pytest.mark.asyncio
async def test_send_patient_event_when_enabled():
    mock_producer = AsyncMock()
    producer = KafkaEventProducer(enabled=True)
    producer._producer = mock_producer
    pid = uuid.uuid4()

    await producer.send_patient_event("lab_appended", pid, {"loinc": "1989-3"})

    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args
    assert args[0] == TOPIC_PATIENT_EVENTS
    assert args[1]["event_type"] == "lab_appended"
    assert args[1]["patient_id"] == str(pid)
    assert args[1]["loinc"] == "1989-3"


@pytest.mark.asyncio
async def test_send_recommendation_served_when_enabled():
    mock_producer = AsyncMock()
    producer = KafkaEventProducer(enabled=True)
    producer._producer = mock_producer
    pid = uuid.uuid4()
    served_at = datetime(2026, 6, 5, tzinfo=timezone.utc)

    await producer.send_recommendation_served(
        session_id="sess-1",
        patient_id=pid,
        model_version="rec-engine-1.0.0",
        nutrient_ids=["vitamin_d3"],
        requires_clinician=False,
        served_at=served_at,
    )

    mock_producer.send_and_wait.assert_called_once()
    args, kwargs = mock_producer.send_and_wait.call_args
    assert args[0] == TOPIC_RECOMMENDATION_SERVED
    assert args[1]["session_id"] == "sess-1"
    assert args[1]["nutrient_ids"] == ["vitamin_d3"]