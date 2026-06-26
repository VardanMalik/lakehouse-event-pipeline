"""Shared :class:`SparkSession` builders for streaming and batch jobs.

The production image bakes Iceberg + S3A configuration into
``spark-defaults.conf`` (see ``infrastructure/spark/spark-defaults.conf``), so
:func:`build_spark_session` deliberately does *not* re-declare all of that. It
only fills in the Iceberg catalog and S3A settings defensively when they are
absent from the active :class:`~pyspark.SparkConf` — for example when a job runs
outside the container in Spark local mode (as the unit tests do).

:func:`build_local_iceberg_session` is a self-contained helper for tests: it
wires a Hadoop-backed Iceberg catalog against a local ``file://`` warehouse so
real Iceberg reads and writes can be exercised without MinIO or Docker.
"""

from __future__ import annotations

from typing import Optional

from pyspark.sql import SparkSession

from lakehouse.common.config import get_settings
from lakehouse.common.logging import get_logger

log = get_logger("lakehouse.streaming.spark_session")

# Iceberg runtime coordinate matching the baked image (Spark 3.5 / Scala 2.12 /
# Iceberg 1.6.1 — see infrastructure/spark/Dockerfile). Used by the local test
# session so Ivy fetches the jar that the production image already bundles.
_ICEBERG_SPARK_RUNTIME = "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1"


def build_spark_session(
    app_name: str, extra_conf: Optional[dict] = None
) -> SparkSession:
    """Build (or return) the shared :class:`SparkSession` for a job.

    Iceberg + S3A configuration is expected to come primarily from the
    image-level ``spark-defaults.conf``. To stay runnable outside the container,
    any of the catalog/S3A keys that are missing from the active
    :class:`~pyspark.SparkConf` are filled in from
    :func:`lakehouse.common.config.get_settings`.

    Args:
        app_name: Spark application name.
        extra_conf: Optional per-job configuration overrides applied last, so
            they win over both the defaults and the defensive fallbacks.

    Returns:
        The configured, active :class:`SparkSession`.
    """
    settings = get_settings()
    catalog = settings.iceberg_catalog_name

    builder = SparkSession.builder.appName(app_name)

    # Defensive defaults: only set a key if it isn't already present in the
    # active SparkConf (i.e. not provided by spark-defaults.conf). This keeps
    # the session runnable in local mode without duplicating image config.
    defensive_conf = {
        "spark.sql.extensions": (
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
        ),
        f"spark.sql.catalog.{catalog}": "org.apache.iceberg.spark.SparkCatalog",
        f"spark.sql.catalog.{catalog}.type": "hadoop",
        f"spark.sql.catalog.{catalog}.warehouse": settings.iceberg_warehouse_path,
        f"spark.sql.catalog.{catalog}.io-impl": "org.apache.iceberg.aws.s3.S3FileIO",
        "spark.sql.defaultCatalog": catalog,
        "spark.hadoop.fs.s3a.endpoint": settings.s3_endpoint,
        "spark.hadoop.fs.s3a.access.key": settings.s3_access_key,
        "spark.hadoop.fs.s3a.secret.key": settings.s3_secret_key,
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
        "spark.hadoop.fs.s3a.aws.credentials.provider": (
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
        ),
    }

    active = SparkSession.getActiveSession()
    existing_conf = dict(active.sparkContext.getConf().getAll()) if active else {}

    for key, value in defensive_conf.items():
        if key not in existing_conf:
            builder = builder.config(key, value)

    # Always pin the session time zone to UTC.
    builder = builder.config("spark.sql.session.timeZone", "UTC")

    if extra_conf:
        for key, value in extra_conf.items():
            builder = builder.config(key, value)

    spark = builder.getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    resolved_warehouse = spark.conf.get(
        f"spark.sql.catalog.{catalog}.warehouse", settings.iceberg_warehouse_path
    )
    log.info(
        "spark_session_built",
        app_name=app_name,
        catalog=catalog,
        warehouse=resolved_warehouse,
    )
    return spark


def build_local_iceberg_session(
    warehouse_dir: str, app_name: str = "test"
) -> SparkSession:
    """Build a local-mode :class:`SparkSession` with a file-backed Iceberg catalog.

    Configures a Hadoop catalog named ``lakehouse`` whose warehouse lives at
    ``file://<warehouse_dir>`` — no S3/MinIO involved — with the Iceberg SQL
    extensions enabled. This lets unit tests perform real Iceberg reads and
    writes against the local filesystem.

    Args:
        warehouse_dir: Local directory to use as the Iceberg warehouse root.
        app_name: Spark application name.

    Returns:
        The configured, active :class:`SparkSession`.
    """
    warehouse_uri = f"file://{warehouse_dir}"

    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[2]")
        .config("spark.jars.packages", _ICEBERG_SPARK_RUNTIME)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config(
            "spark.sql.catalog.lakehouse",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config("spark.sql.catalog.lakehouse.type", "hadoop")
        .config("spark.sql.catalog.lakehouse.warehouse", warehouse_uri)
        .config("spark.sql.defaultCatalog", "lakehouse")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.conf.set("spark.sql.session.timeZone", "UTC")

    log.info(
        "local_iceberg_session_built",
        app_name=app_name,
        catalog="lakehouse",
        warehouse=warehouse_uri,
    )
    return spark
