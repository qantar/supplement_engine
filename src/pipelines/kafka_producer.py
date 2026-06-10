"""Kafka event producers for patient and recommendation lifecycle."""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

TOPIC_PATIENT_EVENTS = "patient.events"
TOPIC_RECOMMENDATION_SERVED = "recommendation.served"


def is_kafka_enabled() -> bool:
    return os.getenv("KAFKA_ENABLED", "0").lower() in ("1", "true", "yes")


class KafkaEventProducer:
    """Fire-and-forget producer; no-op when disabled or broker unreachable."""

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self._bootstrap = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka:29092"
        )
        self._enabled = is_kafka_enabled() if enabled is None else enabled
        self._producer = None

    async def start(self) -> None:
        if not self._enabled:
            logger.info("Kafka producer disabled (KAFKA_ENABLED=0)")
            return
        try:
            from aiokafka import AIOKafkaProducer

            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()
            logger.info("Kafka producer connected to %s", self._bootstrap)
        except Exception as exc:
            logger.warning("Kafka producer unavailable: %s", exc)
            self._producer = None

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send_patient_event(
        self,
        event_type: str,
        patient_id: uuid.UUID,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        payload = {
            "event_type": event_type,
            "patient_id": str(patient_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(extra or {}),
        }
        await self._send(TOPIC_PATIENT_EVENTS, str(patient_id), payload)

    async def send_recommendation_served(
        self,
        session_id: str,
        patient_id: uuid.UUID,
        model_version: str,
        nutrient_ids: list[str],
        requires_clinician: bool,
        served_at: datetime,
    ) -> None:
        payload = {
            "event_type": "recommendation_served",
            "session_id": session_id,
            "patient_id": str(patient_id),
            "nutrient_ids": nutrient_ids,
            "requires_clinician": requires_clinician,
            "model_version": model_version,
            "timestamp": served_at.isoformat(),
        }
        await self._send(TOPIC_RECOMMENDATION_SERVED, session_id, payload)

    async def _send(self, topic: str, key: str, payload: dict[str, Any]) -> None:
        if self._producer is None:
            return
        try:
            await self._producer.send_and_wait(
                topic, payload, key=key.encode("utf-8")
            )
        except Exception as exc:
            logger.warning("Kafka send failed topic=%s: %s", topic, exc)
