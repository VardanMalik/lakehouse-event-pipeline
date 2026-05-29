"""Tests for the ``python -m lakehouse.producer`` CLI."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

import pytest


def test_parse_args_defaults_from_settings():
    from lakehouse.common.config import get_settings
    from lakehouse.producer.__main__ import parse_args

    settings = get_settings()
    ns = parse_args([])
    assert ns.rate == 100
    assert ns.duration == 60
    assert ns.topic == settings.kafka_topic_events
    assert ns.bootstrap_servers == settings.kafka_bootstrap_servers_host
    assert ns.user_pool_size == 1000
    assert ns.seed is None


def test_parse_args_explicit_overrides():
    from lakehouse.producer.__main__ import parse_args

    ns = parse_args(
        [
            "--rate", "500",
            "--duration", "5",
            "--topic", "custom_topic",
            "--bootstrap-servers", "broker:9094",
            "--user-pool-size", "10",
            "--seed", "123",
        ]
    )
    assert ns.rate == 500
    assert ns.duration == 5
    assert ns.topic == "custom_topic"
    assert ns.bootstrap_servers == "broker:9094"
    assert ns.user_pool_size == 10
    assert ns.seed == 123


def test_main_runs_with_mocked_dependencies(monkeypatch: pytest.MonkeyPatch):
    from lakehouse.producer import __main__ as main_mod

    publisher_instance = MagicMock()
    publisher_instance.total_sent = 0
    publisher_instance.total_delivered = 0
    publisher_instance.total_failed = 0
    publisher_instance.metrics.return_value = {
        "total_sent": 0,
        "total_delivered": 0,
        "total_failed": 0,
        "current_rate": 0.0,
    }
    publisher_cls = MagicMock(return_value=publisher_instance)

    generator_instance = MagicMock()
    call_count = {"n": 0}

    def fake_generate() -> MagicMock:
        call_count["n"] += 1
        if call_count["n"] >= 3:
            raise KeyboardInterrupt
        return MagicMock()

    generator_instance.generate_event.side_effect = fake_generate
    generator_cls = MagicMock(return_value=generator_instance)

    with patch.object(main_mod, "EventPublisher", publisher_cls), patch.object(
        main_mod, "EventGenerator", generator_cls
    ), patch.object(main_mod.time, "sleep"), pytest.raises(KeyboardInterrupt):
        main_mod.main(
            ["--rate", "10", "--duration", "0", "--topic", "t", "--seed", "1"]
        )

    publisher_cls.assert_called_once()
    publisher_cls.assert_called_with(bootstrap_servers=ANY, topic="t")
    generator_cls.assert_called_once_with(user_pool_size=1000, seed=1)
    publisher_instance.flush.assert_called_once()
