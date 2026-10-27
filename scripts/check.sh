#!/usr/bin/env bash
# Единая точка входа для проверок проекта.
#
# Использование:
#   ./scripts/check.sh           все проверки
#   ./scripts/check.sh docs      только документация
#
# Источники:
# - https://google.github.io/styleguide/shellguide.html
# - https://www.shellcheck.net/

set -euo pipefail

main() {
  local root status check name filter
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  status=0

  case "${1:-all}" in
    all) filter="" ;;
    docs) filter="docs" ;;
    *) printf 'неизвестный набор: %s (all|docs)\n' "$1" >&2; return 2 ;;
  esac

  shopt -s nullglob
  for check in "$root"/scripts/checks/*.sh; do
    name="$(basename "$check")"
    case "$name" in
      _*) continue ;;
    esac
    if [[ -n "$filter" && "$name" != "$filter"* ]]; then
      continue
    fi
    printf '== %s\n' "$name"
    "$check" || status=$?
  done

  return "$status"
}

main "$@"
