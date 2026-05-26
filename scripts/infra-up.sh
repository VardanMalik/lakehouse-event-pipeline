#!/usr/bin/env bash
# Bring up the local lakehouse infrastructure and wait for it to become healthy.
# Exits 0 when every service is healthy or, for the one-shot init job, exited cleanly.
# Exits non-zero if any service fails to reach that state within the timeout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

TIMEOUT_SECONDS="${INFRA_UP_TIMEOUT:-60}"
POLL_INTERVAL_SECONDS=2

# Services that ship a healthcheck — they must report "healthy".
HEALTHCHECK_SERVICES=("kafka" "minio")
# Services without a healthcheck — they only need to be "running".
RUNNING_SERVICES=("zookeeper" "kafka-ui")
# One-shot init jobs — success is "exited" with code 0.
INIT_SERVICES=("minio-init")

echo ">>> Starting infrastructure via docker compose"
docker compose -f "${COMPOSE_FILE}" up -d

container_state() {
    # Prints the container's .State.Status (running, exited, ...) or empty if missing.
    local service="$1"
    local cid
    cid="$(docker compose -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then
        echo ""
        return
    fi
    docker inspect -f '{{.State.Status}}' "${cid}" 2>/dev/null || echo ""
}

container_health() {
    # Prints the container's .State.Health.Status (healthy, unhealthy, starting),
    # or "none" if the container has no healthcheck.
    local service="$1"
    local cid
    cid="$(docker compose -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then
        echo "missing"
        return
    fi
    docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${cid}" 2>/dev/null || echo "unknown"
}

container_exit_code() {
    local service="$1"
    local cid
    cid="$(docker compose -f "${COMPOSE_FILE}" ps -q "${service}" 2>/dev/null || true)"
    if [[ -z "${cid}" ]]; then
        echo "-1"
        return
    fi
    docker inspect -f '{{.State.ExitCode}}' "${cid}" 2>/dev/null || echo "-1"
}

all_ready() {
    local svc state health code

    for svc in "${HEALTHCHECK_SERVICES[@]}"; do
        health="$(container_health "${svc}")"
        if [[ "${health}" != "healthy" ]]; then
            return 1
        fi
    done

    for svc in "${RUNNING_SERVICES[@]}"; do
        state="$(container_state "${svc}")"
        if [[ "${state}" != "running" ]]; then
            return 1
        fi
    done

    for svc in "${INIT_SERVICES[@]}"; do
        state="$(container_state "${svc}")"
        if [[ "${state}" == "exited" ]]; then
            code="$(container_exit_code "${svc}")"
            if [[ "${code}" != "0" ]]; then
                return 2
            fi
        else
            return 1
        fi
    done

    return 0
}

echo ">>> Waiting up to ${TIMEOUT_SECONDS}s for services to become ready"
elapsed=0
while (( elapsed < TIMEOUT_SECONDS )); do
    set +e
    all_ready
    rc=$?
    set -e

    case "${rc}" in
        0)
            echo ">>> All services are ready"
            docker compose -f "${COMPOSE_FILE}" ps
            exit 0
            ;;
        2)
            echo "!!! An init service exited with a non-zero status" >&2
            docker compose -f "${COMPOSE_FILE}" ps
            for svc in "${INIT_SERVICES[@]}"; do
                echo "--- logs: ${svc} ---" >&2
                docker compose -f "${COMPOSE_FILE}" logs --no-color "${svc}" >&2 || true
            done
            exit 1
            ;;
    esac

    sleep "${POLL_INTERVAL_SECONDS}"
    elapsed=$(( elapsed + POLL_INTERVAL_SECONDS ))
done

echo "!!! Timed out after ${TIMEOUT_SECONDS}s waiting for services to become ready" >&2
docker compose -f "${COMPOSE_FILE}" ps >&2
for svc in "${HEALTHCHECK_SERVICES[@]}" "${RUNNING_SERVICES[@]}" "${INIT_SERVICES[@]}"; do
    echo "--- logs: ${svc} (tail 50) ---" >&2
    docker compose -f "${COMPOSE_FILE}" logs --no-color --tail=50 "${svc}" >&2 || true
done
exit 1
