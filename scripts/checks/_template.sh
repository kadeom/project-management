#!/usr/bin/env bash
# Шаблон проверки. Файлы с префиксом _ не запускаются check.sh.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Проверка должна вернуть 0 при успехе и ненулевой код при ошибке.
printf 'template: пропущено (root=%s)\n' "$root"
exit 0
