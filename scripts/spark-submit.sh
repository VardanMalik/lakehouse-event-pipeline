#!/usr/bin/env bash
# Run spark-submit against a Python script that lives in this repo.
#
# Usage:
#   ./scripts/spark-submit.sh <path/to/script.py> [extra spark-submit args ...]
#
# The path is interpreted relative to the project root. The script is reachable
# inside the container at /opt/spark-apps/<relative-path> because docker-compose
# bind-mounts the repo root read-only to /opt/spark-apps.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $(basename "$0") <path/to/script.py> [spark-submit args ...]" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

REL_SCRIPT="$1"
shift

# Reject absolute paths and any attempt to escape the repo root.
if [[ "${REL_SCRIPT}" == /* || "${REL_SCRIPT}" == *".."* ]]; then
    echo "Error: script path must be relative to the project root and may not contain '..'" >&2
    exit 2
fi

# Verify the file exists on the host so we fail fast with a clear message
# rather than a cryptic spark-submit error.
if [[ ! -f "${REPO_ROOT}/${REL_SCRIPT}" ]]; then
    echo "Error: ${REPO_ROOT}/${REL_SCRIPT} does not exist" >&2
    exit 2
fi

CONTAINER_PATH="/opt/spark-apps/${REL_SCRIPT}"

exec docker compose -f "${COMPOSE_FILE}" exec spark \
    /opt/spark/bin/spark-submit "$@" "${CONTAINER_PATH}"
