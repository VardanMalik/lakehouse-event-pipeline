#!/usr/bin/env bash
set -euo pipefail
exec python -m lakehouse.producer "$@"
