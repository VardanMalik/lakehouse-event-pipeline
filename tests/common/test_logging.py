"""Tests for :mod:`lakehouse.common.logging`."""

from __future__ import annotations

import json

import pytest

from lakehouse.common.config import Settings
from lakehouse.common.logging import configure_logging, get_logger


def test_json_mode_emits_valid_json(capsys: pytest.CaptureFixture[str]):
    settings = Settings(log_format="json", log_level="INFO")
    configure_logging(settings)

    logger = get_logger("test.json")
    logger.info("hello", user_id="u-1")

    out = capsys.readouterr().out.strip().splitlines()
    assert out, "expected at least one log line on stdout"

    payload = json.loads(out[-1])
    assert payload["event"] == "hello"
    assert payload["user_id"] == "u-1"
    assert payload["level"] == "info"
    assert payload["logger"] == "test.json"
    assert "timestamp" in payload


def test_console_mode_emits_human_readable(capsys: pytest.CaptureFixture[str]):
    settings = Settings(log_format="console", log_level="INFO")
    configure_logging(settings)

    logger = get_logger("test.console")
    logger.info("hello-console", user_id="u-2")

    out = capsys.readouterr().out
    assert "hello-console" in out
    assert "u-2" in out

    last_line = out.strip().splitlines()[-1]
    with pytest.raises(json.JSONDecodeError):
        json.loads(last_line)
