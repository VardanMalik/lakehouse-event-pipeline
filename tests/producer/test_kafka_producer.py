"""Tests for :mod:`lakehouse.producer.kafka_producer`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from lakehouse.common.schemas import CustomerEvent


def _make_event() -> CustomerEvent:
    return CustomerEvent(
        event_id=str(uuid4()),
        user_id="user-xyz",
        session_id="sess-1",
        event_type="page_view",
        event_timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        page_url="https://example.com/",
        referrer=None,
        device_type="desktop",
        country="US",
        properties={},
        revenue_usd=None,
    )


@pytest.fixture()
def mock_producer_cls():
    with patch("lakehouse.producer.kafka_producer.Producer") as cls:
        cls.return_value = MagicMock()
        yield cls


def test_publish_calls_produce_with_correct_args(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    event = _make_event()

    publisher.publish(event)

    inner = mock_producer_cls.return_value
    inner.produce.assert_called_once()
    kwargs = inner.produce.call_args.kwargs
    args = inner.produce.call_args.args
    assert args[0] == "t"
    assert kwargs["key"] == event.user_id.encode("utf-8")
    assert kwargs["value"] == event.to_kafka_json().encode("utf-8")
    assert json.loads(kwargs["value"]) == json.loads(event.to_kafka_json())
    assert kwargs["on_delivery"] == publisher._delivery_callback
    inner.poll.assert_called_once_with(0)
    assert publisher.total_sent == 1


def test_delivery_callback_success_increments_delivered(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    msg = MagicMock()
    msg.topic.return_value = "t"
    msg.partition.return_value = 0
    msg.offset.return_value = 7

    publisher._delivery_callback(None, msg)

    assert publisher.total_delivered == 1
    assert publisher.total_failed == 0


def test_delivery_callback_error_increments_failed(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    msg = MagicMock()
    msg.topic.return_value = "t"
    msg.partition.return_value = 0
    msg.offset.return_value = None

    publisher._delivery_callback(RuntimeError("boom"), msg)

    assert publisher.total_failed == 1
    assert publisher.total_delivered == 0


def test_current_rate_zero_before_any_publish(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    assert publisher.current_rate() == 0.0


def test_current_rate_positive_after_burst(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    for _ in range(25):
        publisher.publish(_make_event())
    assert publisher.current_rate() > 0.0


def test_flush_forwards_timeout(mock_producer_cls):
    from lakehouse.producer.kafka_producer import EventPublisher

    publisher = EventPublisher(bootstrap_servers="b:9092", topic="t")
    publisher.flush(timeout=3.5)
    mock_producer_cls.return_value.flush.assert_called_once_with(3.5)
