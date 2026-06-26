#!/usr/bin/env bash
# Consume a small number of messages from a Kafka topic for manual inspection.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infrastructure/docker-compose.yml"

TOPIC="customer_events"
MAX_MESSAGES=20
TIMEOUT_SECONDS=10

usage() {
    cat <<EOF
Usage: $(basename "$0") [--topic NAME] [--max-messages N] [--timeout-seconds N]

Defaults:
  --topic            customer_events
  --max-messages     20
  --timeout-seconds  10
EOF
}

while (("$#")); do
    case "$1" in
        --topic)
            TOPIC="$2"; shift 2 ;;
        --max-messages)
            MAX_MESSAGES="$2"; shift 2 ;;
        --timeout-seconds)
            TIMEOUT_SECONDS="$2"; shift 2 ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2 ;;
    esac
done

TIMEOUT_MS=$((TIMEOUT_SECONDS * 1000))

consume() {
    docker compose -f "${COMPOSE_FILE}" exec -T kafka kafka-console-consumer \
        --bootstrap-server kafka:29092 \
        --topic "${TOPIC}" \
        --from-beginning \
        --max-messages "${MAX_MESSAGES}" \
        --timeout-ms "${TIMEOUT_MS}" \
        --property print.key=true \
        --property print.timestamp=true \
        --property key.separator=" | "
}

if command -v jq >/dev/null 2>&1; then
    # Each line is "CreateTime:... | key | json_value". jq only handles the JSON
    # tail, so split on the last " | " and pretty-print the value.
    consume | awk -F' \\| ' '{
        prefix = $1 " | " $2;
        value = $0;
        sub(/^[^|]*\| [^|]*\| /, "", value);
        printf "%s\n%s\n---\n", prefix, value;
    }' | while IFS= read -r line; do
        if [[ "${line}" == "---" ]]; then
            echo "---"
        elif [[ "${line}" =~ ^\{ ]]; then
            echo "${line}" | jq .
        else
            echo "${line}"
        fi
    done
else
    consume
fi
