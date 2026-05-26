#!/usr/bin/env bash
# Tear down the local lakehouse infrastructure.
# By default keeps named volumes (so MinIO data persists across restarts).
# Pass --clean to also remove named volumes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

CLEAN=0
for arg in "$@"; do
    case "${arg}" in
        --clean)
            CLEAN=1
            ;;
        -h|--help)
            cat <<'USAGE'
Usage: infra-down.sh [--clean]

  --clean   Also remove named volumes (drops MinIO data).
            Without this flag, containers and the network are removed
            but volumes are preserved.
USAGE
            exit 0
            ;;
        *)
            echo "Unknown argument: ${arg}" >&2
            echo "Run 'infra-down.sh --help' for usage." >&2
            exit 2
            ;;
    esac
done

if (( CLEAN == 1 )); then
    echo ">>> Stopping infrastructure and removing volumes"
    docker compose -f "${COMPOSE_FILE}" down --volumes --remove-orphans
else
    echo ">>> Stopping infrastructure (volumes preserved)"
    docker compose -f "${COMPOSE_FILE}" down --remove-orphans
fi

echo ">>> Done"
