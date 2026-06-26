#!/usr/bin/env bash
# Describe a single Kafka topic: partitions, replication, configs, leader/ISR.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

if [[ $# -lt 1 ]]; then
    echo "Usage: $(basename "$0") TOPIC_NAME" >&2
    exit 2
fi

TOPIC="$1"

docker compose -f "${COMPOSE_FILE}" exec -T kafka \
    kafka-topics --describe --bootstrap-server kafka:29092 --topic "${TOPIC}"
