#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" scripts/probe_gui_controls.py "$@"
