#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
 --help) echo 'Usage: bootstrap.sh [--dry-run|--full-upstream]. Default installs lightweight project dependencies. Full upstream sync requires Linux x86_64.'; exit 0;;
 --dry-run) echo 'Would verify pinned CADWORLD commit, uv sync local dependencies, and run upstream CLI unit tests; no VM/model downloads.'; exit 0;;
 --full-upstream) test "$(uname -s)" = Linux && test "$(uname -m)" = x86_64 || exit 2;;
 '') ;;
 *) echo 'Unknown argument' >&2; exit 2;;
esac
pin=e5d0ebab8bd28da6e98c68c61db05747d1647f7b
submodule_mode=$(git ls-files --stage -- vendor/CADWORLD | cut -d ' ' -f 1)
if test "$submodule_mode" = 160000 && test ! -e vendor/CADWORLD/.git; then
 git submodule update --init -- vendor/CADWORLD
elif test ! -e vendor/CADWORLD/.git; then
 mkdir -p vendor
 git clone --filter=blob:none --no-checkout https://github.com/Zdong104/CADWORLD.git vendor/CADWORLD
 git -C vendor/CADWORLD fetch origin "$pin"
 git -C vendor/CADWORLD checkout --detach "$pin"
fi
test "$(git -C vendor/CADWORLD rev-parse HEAD)" = "$pin"
test -z "$(git -C vendor/CADWORLD status --porcelain --untracked-files=no)"
uv sync --frozen
PYTHONPATH=vendor/CADWORLD .venv/bin/python -m unittest CLI.test_terminal_agent
if test "${1:-}" = --full-upstream; then
 (cd vendor/CADWORLD && uv sync --frozen && uv run python -m unittest CLI.test_terminal_agent && uv run python CLI/run_cli.py --dry-run)
fi
