"""Tests for :mod:`lakehouse.common.config`."""

from __future__ import annotations

import pytest

from lakehouse.common.config import Settings, get_settings


def test_defaults_when_no_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path, chdir_tmp):
    settings = Settings()
    assert settings.kafka_bootstrap_servers == "kafka:29092"
    assert settings.kafka_bootstrap_servers_host == "localhost:9092"
    assert settings.kafka_topic_events == "customer_events"
    assert settings.kafka_topic_dlq == "customer_events_dlq"
    assert settings.s3_endpoint == "http://minio:9000"
    assert settings.s3_endpoint_host == "http://localhost:9000"
    assert settings.s3_access_key == "minioadmin"
    assert settings.s3_secret_key == "minioadmin"
    assert settings.s3_bucket == "lakehouse-warehouse"
    assert settings.iceberg_warehouse_path == "s3a://lakehouse-warehouse/"
    assert settings.iceberg_catalog_name == "lakehouse"
    assert settings.iceberg_table_events == "lakehouse.events.customer_events"
    assert settings.iceberg_table_features == "lakehouse.features.user_features"
    assert settings.log_level == "INFO"
    assert settings.log_format == "console"


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch, chdir_tmp):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:9094")
    monkeypatch.setenv("S3_BUCKET", "my-bucket")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()
    assert settings.kafka_bootstrap_servers == "broker:9094"
    assert settings.s3_bucket == "my-bucket"
    assert settings.log_format == "json"
    assert settings.log_level == "DEBUG"


def test_env_vars_are_case_insensitive(monkeypatch: pytest.MonkeyPatch, chdir_tmp):
    monkeypatch.setenv("kafka_topic_events", "lowercase_topic")
    settings = Settings()
    assert settings.kafka_topic_events == "lowercase_topic"


def test_get_settings_returns_same_instance(chdir_tmp):
    first = get_settings()
    second = get_settings()
    assert first is second
