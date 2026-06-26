#!/usr/bin/env bash
# Create (idempotently) the Iceberg customer-events table inside the spark
# container via spark-submit. Extra args are forwarded to the bootstrap job,
# e.g. ./scripts/bootstrap-iceberg.sh --table lakehouse.events.customer_events
set -euo pipefail

docker compose -f infrastructure/docker-compose.yml exec -T spark \
    /opt/spark/bin/spark-submit /opt/spark-apps/src/lakehouse/streaming/bootstrap.py "$@"
