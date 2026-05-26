#!/usr/bin/env bash
# Open an interactive PySpark REPL inside the running `spark` container.
# The container must already be up — run scripts/infra-up.sh first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

exec docker compose -f "${COMPOSE_FILE}" exec spark /opt/spark/bin/pyspark
