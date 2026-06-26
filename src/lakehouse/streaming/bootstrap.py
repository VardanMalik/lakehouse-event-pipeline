"""Bootstrap the Iceberg target table for customer events.

Running this module (or :func:`main`) is idempotent: it creates the parent
namespace and the events table only if they do not already exist, so it is safe
to re-run against an existing warehouse.
"""

from __future__ import annotations

import argparse
from typing import Optional

from pyspark.sql import SparkSession

from lakehouse.common.config import get_settings
from lakehouse.common.logging import configure_logging, get_logger
from lakehouse.streaming.spark_session import build_spark_session

log = get_logger("lakehouse.streaming.bootstrap")


def bootstrap_events_table(spark: SparkSession, table: str) -> None:
    """Create the Iceberg events table (and its namespace) if absent.

    The table uses Iceberg *hidden partitioning*: ``PARTITIONED BY
    (days(event_timestamp), event_type)`` declares two partition transforms
    directly on data columns. There is therefore **no separate partition
    column** — the daily bucket is derived from ``event_timestamp`` by the
    ``days()`` transform at write time. The ``ingest_date`` column is an
    ordinary stored ``DATE`` kept for convenient querying/filtering; it is *not*
    the partition key and is unrelated to the partition spec.

    Args:
        spark: An active :class:`SparkSession` with the Iceberg catalog wired.
        table: Fully-qualified table identifier, e.g.
            ``lakehouse.events.customer_events``.
    """
    namespace = ".".join(table.split(".")[:-1])

    log.info("bootstrap_namespace_create", namespace=namespace)
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {namespace}")

    log.info("bootstrap_table_create", table=table)
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            event_id STRING,
            user_id STRING,
            session_id STRING,
            event_type STRING,
            event_timestamp TIMESTAMP,
            page_url STRING,
            referrer STRING,
            device_type STRING,
            country STRING,
            properties MAP<STRING, STRING>,
            revenue_usd DOUBLE,
            ingest_timestamp TIMESTAMP,
            ingest_date DATE
        )
        USING iceberg
        PARTITIONED BY (days(event_timestamp), event_type)
        TBLPROPERTIES (
            'write.format.default'='parquet',
            'write.parquet.compression-codec'='zstd',
            'format-version'='2',
            'write.metadata.delete-after-commit.enabled'='true',
            'write.metadata.previous-versions-max'='10'
        )
        """
    )

    describe_rows = spark.sql(f"DESCRIBE EXTENDED {table}").collect()
    schema_lines = [
        f"{row['col_name']}: {row['data_type']}"
        for row in describe_rows
        if row["col_name"] and not row["col_name"].startswith("#")
    ]
    log.info(
        "bootstrap_table_described",
        table=table,
        schema=schema_lines,
        partition_spec=describe_partition_spec(spark, table),
    )


def describe_partition_spec(spark: SparkSession, table: str) -> list[str]:
    """Extract the partition transforms from ``DESCRIBE EXTENDED`` output.

    Returns the human-readable transform expressions (e.g. ``days(event_timestamp)``,
    ``event_type``) declared in the table's partition spec.
    """
    rows = spark.sql(f"DESCRIBE EXTENDED {table}").collect()
    transforms: list[str] = []
    in_partition_section = False
    for row in rows:
        name = (row["col_name"] or "").strip()
        if name.startswith("# Partition"):
            in_partition_section = True
            continue
        if in_partition_section:
            if not name or name.startswith("#"):
                break
            transforms.append((row["data_type"] or "").strip())
    return transforms


def main(argv: Optional[list[str]] = None) -> int:
    settings = get_settings()
    configure_logging(settings)

    parser = argparse.ArgumentParser(
        prog="lakehouse.streaming.bootstrap",
        description="Create the Iceberg customer-events table if it does not exist.",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=settings.iceberg_table_events,
        help="Fully-qualified Iceberg table to bootstrap.",
    )
    args = parser.parse_args(argv)

    spark = build_spark_session("bootstrap-events-table")
    try:
        bootstrap_events_table(spark, args.table)
        partition_spec = describe_partition_spec(spark, args.table)
        log.info(
            "bootstrap_complete",
            table=args.table,
            partition_spec=partition_spec,
        )
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
