"""Real Iceberg integration tests for the events-table bootstrap.

These run against a local ``file://`` Iceberg warehouse (see the
``local_iceberg_spark`` fixture) — no Docker or MinIO required — but they do
need Java and PySpark available locally, so they are marked ``spark``.
"""

from __future__ import annotations

import pytest

from lakehouse.streaming.bootstrap import (
    bootstrap_events_table,
    describe_partition_spec,
)

pytestmark = pytest.mark.spark

TABLE = "lakehouse.events.customer_events"


def test_bootstrap_creates_table(local_iceberg_spark) -> None:
    bootstrap_events_table(local_iceberg_spark, TABLE)

    tables = [
        row["tableName"]
        for row in local_iceberg_spark.sql("SHOW TABLES IN lakehouse.events").collect()
    ]
    assert "customer_events" in tables


def test_partition_spec_includes_days_and_event_type(local_iceberg_spark) -> None:
    bootstrap_events_table(local_iceberg_spark, TABLE)

    spec = describe_partition_spec(local_iceberg_spark, TABLE)
    joined = " ".join(spec)
    assert "days(event_timestamp)" in joined
    assert "event_type" in joined


def test_bootstrap_is_idempotent(local_iceberg_spark) -> None:
    bootstrap_events_table(local_iceberg_spark, TABLE)
    # A second call must not raise (CREATE ... IF NOT EXISTS).
    bootstrap_events_table(local_iceberg_spark, TABLE)

    tables = [
        row["tableName"]
        for row in local_iceberg_spark.sql("SHOW TABLES IN lakehouse.events").collect()
    ]
    assert tables.count("customer_events") == 1


def test_insert_and_read_back_roundtrips(local_iceberg_spark) -> None:
    bootstrap_events_table(local_iceberg_spark, TABLE)

    local_iceberg_spark.sql(
        f"""
        INSERT INTO {TABLE}
        SELECT
            'evt-1' AS event_id,
            'user-1' AS user_id,
            'sess-1' AS session_id,
            'page_view' AS event_type,
            TIMESTAMP '2026-01-01 12:00:00' AS event_timestamp,
            'https://example.com/' AS page_url,
            CAST(NULL AS STRING) AS referrer,
            'desktop' AS device_type,
            'US' AS country,
            map('campaign', 'spring') AS properties,
            CAST(NULL AS DOUBLE) AS revenue_usd,
            TIMESTAMP '2026-01-01 12:00:05' AS ingest_timestamp,
            DATE '2026-01-01' AS ingest_date
        """
    )

    rows = local_iceberg_spark.sql(
        f"SELECT event_id, user_id, event_type, country, properties, ingest_date "
        f"FROM {TABLE} WHERE event_id = 'evt-1'"
    ).collect()

    assert len(rows) == 1
    row = rows[0]
    assert row["event_id"] == "evt-1"
    assert row["user_id"] == "user-1"
    assert row["event_type"] == "page_view"
    assert row["country"] == "US"
    assert row["properties"] == {"campaign": "spring"}
    assert str(row["ingest_date"]) == "2026-01-01"
