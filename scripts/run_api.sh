#!/usr/bin/env bash
# Google Cloud Shell: from repo root
#   chmod +x scripts/phase2_run_api.sh
#   ./scripts/phase2_run_api.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.:adk_agents
# shellcheck source=/dev/null
source .venv/bin/activate
exec uvicorn sprint_api.main:app --host 0.0.0.0 --port 8080
