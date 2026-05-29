"""PySpark schemas that mirror the Pydantic models in :mod:`lakehouse.common.schemas`.

Mapping to :class:`lakehouse.common.schemas.CustomerEvent`:

    Pydantic field        Spark field        Spark type
    --------------------  -----------------  --------------------------------
    event_id              event_id           StringType
    user_id               user_id            StringType
    session_id            session_id         StringType
    event_type            event_type         StringType  (Literal enforced upstream)
    event_timestamp       event_timestamp    TimestampType (UTC)
    page_url              page_url           StringType (nullable)
    referrer              referrer           StringType (nullable)
    device_type           device_type        StringType  (Literal enforced upstream)
    country               country            StringType  (ISO-2, enforced upstream)
    properties            properties         MapType(StringType, StringType)
                                              -- nested values are flattened to
                                              -- strings at parse time.
    revenue_usd           revenue_usd        DoubleType (nullable)
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    MapType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


CUSTOMER_EVENT_SCHEMA: StructType = StructType(
    [
        StructField("event_id", StringType(), nullable=False),
        StructField("user_id", StringType(), nullable=False),
        StructField("session_id", StringType(), nullable=False),
        StructField("event_type", StringType(), nullable=False),
        StructField("event_timestamp", TimestampType(), nullable=False),
        StructField("page_url", StringType(), nullable=True),
        StructField("referrer", StringType(), nullable=True),
        StructField("device_type", StringType(), nullable=False),
        StructField("country", StringType(), nullable=False),
        StructField(
            "properties",
            MapType(StringType(), StringType(), valueContainsNull=True),
            nullable=False,
        ),
        StructField("revenue_usd", DoubleType(), nullable=True),
    ]
)
