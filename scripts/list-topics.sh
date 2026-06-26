#!/usr/bin/env bash
# List all Kafka topics on the local broker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

docker compose -f "${COMPOSE_FILE}" exec -T kafka \
    kafka-topics --list --bootstrap-server kafka:29092
