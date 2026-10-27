#!/usr/bin/env bash
# Проверка: pytest и ruff.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

if ! python3 -c "import pytest" >/dev/null 2>&1; then
  printf 'python: pytest не установлен — pip install -r requirements.txt\n' >&2
  exit 1
fi

if ! command -v ruff >/dev/null 2>&1; then
  printf 'python: ruff не установлен — pip install -r requirements.txt\n' >&2
  exit 1
fi

ruff check src/pm automation tests build_infosec.py scripts additional-assignment
python3 -m pytest tests -q
