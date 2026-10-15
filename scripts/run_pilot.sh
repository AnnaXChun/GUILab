#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m cad_cf.counterfactual --config configs/pilot.yaml "$@"
