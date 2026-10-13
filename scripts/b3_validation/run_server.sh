#!/usr/bin/env bash
# Start the B3.2 healthz server. Reads token from env (must already be set).
# Usage:
#   export ICYQUANT_MT5_TOKEN="<random-32+>"
#   ./run_server.sh
set -euo pipefail

if [[ -z "${ICYQUANT_MT5_TOKEN:-}" ]]; then
    echo "[FATAL] ICYQUANT_MT5_TOKEN is not set. Refusing to start." >&2
    exit 2
fi

cd "$(dirname "$0")"
exec python3 healthz_server.py
