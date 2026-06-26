#!/usr/bin/env bash
# Idempotently create the Kafka topics this project relies on.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"
BOOTSTRAP="kafka:29092"

kafka_exec() {
    docker compose -f "${COMPOSE_FILE}" exec -T kafka "$@"
}

ensure_kafka_running() {
    local cid
    cid="$(docker compose -f "${COMPOSE_FILE}" ps -q kafka 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then
        echo "!!! kafka container is not running." >&2
        echo "    Bring infrastructure up first: make infra-up" >&2
        exit 1
    fi
    local state
    state="$(docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null || echo "")"
    if [[ "${state}" != "running" ]]; then
        echo "!!! kafka container state is '${state}', expected 'running'." >&2
        echo "    Bring infrastructure up first: make infra-up" >&2
        exit 1
    fi
}

topic_exists() {
    local topic="$1"
    kafka_exec kafka-topics \
        --bootstrap-server "${BOOTSTRAP}" \
        --describe \
        --topic "${topic}" >/dev/null 2>&1
}

create_topic() {
    local topic="$1"
    local partitions="$2"
    local replication="$3"
    shift 3
    local -a configs=()
    while (("$#")); do
        configs+=(--config "$1")
        shift
    done

    if topic_exists "${topic}"; then
        echo ">>> Topic ${topic} already exists, skipping"
        return 0
    fi

    echo ">>> Creating topic ${topic} (partitions=${partitions}, replication=${replication})"
    kafka_exec kafka-topics \
        --bootstrap-server "${BOOTSTRAP}" \
        --create \
        --topic "${topic}" \
        --partitions "${partitions}" \
        --replication-factor "${replication}" \
        "${configs[@]}"
}

ensure_kafka_running

create_topic "customer_events" 6 1 \
    "retention.ms=604800000" \
    "compression.type=producer"

create_topic "customer_events_dlq" 3 1 \
    "retention.ms=1209600000" \
    "compression.type=producer"

echo ""
echo ">>> Final topic list:"
kafka_exec kafka-topics --list --bootstrap-server "${BOOTSTRAP}"
