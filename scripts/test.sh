#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
 --help) echo 'Usage: test.sh [--dry-run]. Runs local deterministic pytest and pinned CLI unit tests.'; exit 0;;
 --dry-run) echo '.venv/bin/pytest -q tests'; echo 'PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent'; exit 0;;
 '') ;;
 *) echo 'Unknown argument' >&2; exit 2;;
esac
.venv/bin/pytest -q tests
PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
