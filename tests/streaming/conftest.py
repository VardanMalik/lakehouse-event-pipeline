"""Fixtures for streaming tests that exercise a real local Iceberg session."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def local_iceberg_spark() -> Iterator[object]:
    """Session-scoped local Iceberg :class:`SparkSession` over a temp warehouse.

    Builds a Hadoop-catalog Iceberg session backed by a temporary ``file://``
    warehouse so tests can do real Iceberg reads/writes without MinIO/Docker.
    The session is stopped and the warehouse removed on teardown.

    The PySpark import is deferred into the fixture body so that collecting the
    rest of the suite does not require PySpark to be installed.
    """
    from lakehouse.streaming.spark_session import build_local_iceberg_session

    warehouse_dir = tempfile.mkdtemp(prefix="iceberg-warehouse-")
    spark = build_local_iceberg_session(warehouse_dir)
    try:
        yield spark
    finally:
        spark.stop()
        shutil.rmtree(warehouse_dir, ignore_errors=True)
