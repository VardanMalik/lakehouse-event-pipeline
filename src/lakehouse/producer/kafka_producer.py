"""Kafka publisher built on confluent_kafka.Producer."""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Optional

from confluent_kafka import Producer

from lakehouse.common.logging import get_logger
from lakehouse.common.schemas import CustomerEvent


RATE_WINDOW_SECONDS = 5.0


class EventPublisher:
    """Buffer-friendly Kafka publisher with structured-log delivery callbacks."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        linger_ms: int = 50,
        batch_size: int = 16384,
        acks: str = "all",
        compression_type: str = "lz4",
        extra_config: Optional[dict[str, Any]] = None,
    ) -> None:
        self._topic = topic
        self._log = get_logger("lakehouse.producer.kafka")

        config: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers,
            "linger.ms": linger_ms,
            "batch.size": batch_size,
            "acks": acks,
            "compression.type": compression_type,
        }
        if extra_config:
            config.update(extra_config)

        self._producer = Producer(config)

        self.total_sent: int = 0
        self.total_delivered: int = 0
        self.total_failed: int = 0
        self._send_times: deque[float] = deque()

    @property
    def topic(self) -> str:
        return self._topic

    def publish(self, event: CustomerEvent) -> None:
        payload = event.to_kafka_json().encode("utf-8")
        key = event.user_id.encode("utf-8")
        self._producer.produce(
            self._topic,
            key=key,
            value=payload,
            on_delivery=self._delivery_callback,
        )
        self._producer.poll(0)
        self.total_sent += 1
        self._record_send(time.monotonic())

    def _record_send(self, now: float) -> None:
        self._send_times.append(now)
        cutoff = now - RATE_WINDOW_SECONDS
        while self._send_times and self._send_times[0] < cutoff:
            self._send_times.popleft()

    def _delivery_callback(self, err, msg) -> None:
        if err is not None:
            self.total_failed += 1
            self._log.warning(
                "kafka_delivery_failed",
                topic=getattr(msg, "topic", lambda: self._topic)(),
                partition=getattr(msg, "partition", lambda: None)(),
                offset=getattr(msg, "offset", lambda: None)(),
                error=str(err),
            )
            return
        self.total_delivered += 1
        self._log.debug(
            "kafka_delivery_ok",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )

    def flush(self, timeout: float = 10.0) -> int:
        return self._producer.flush(timeout)

    def current_rate(self) -> float:
        if not self._send_times:
            return 0.0
        now = time.monotonic()
        cutoff = now - RATE_WINDOW_SECONDS
        while self._send_times and self._send_times[0] < cutoff:
            self._send_times.popleft()
        if not self._send_times:
            return 0.0
        elapsed = max(now - self._send_times[0], 1e-6)
        return len(self._send_times) / elapsed

    def metrics(self) -> dict[str, Any]:
        return {
            "total_sent": self.total_sent,
            "total_delivered": self.total_delivered,
            "total_failed": self.total_failed,
            "current_rate": self.current_rate(),
        }
