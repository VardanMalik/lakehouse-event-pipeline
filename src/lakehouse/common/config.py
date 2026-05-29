"""Application settings loaded from environment variables and ``.env``."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the lakehouse pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_bootstrap_servers_host: str = "localhost:9092"
    kafka_topic_events: str = "customer_events"
    kafka_topic_dlq: str = "customer_events_dlq"

    s3_endpoint: str = "http://minio:9000"
    s3_endpoint_host: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "lakehouse-warehouse"

    iceberg_warehouse_path: str = "s3a://lakehouse-warehouse/"
    iceberg_catalog_name: str = "lakehouse"
    iceberg_table_events: str = "lakehouse.events.customer_events"
    iceberg_table_features: str = "lakehouse.features.user_features"

    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
