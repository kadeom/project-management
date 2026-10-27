#!/usr/bin/env bash
# Проверка: относительные Markdown-ссылки в документации существуют.
# URL-кодирование (%20) раскодируется, чтобы ссылки на файлы с пробелами работали.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$root" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

root = Path(sys.argv[1])
link_re = re.compile(r"\]\(([^)]+)\)")
bad = 0
checked = 0

for md in sorted(root.rglob("*.md")):
    if ".git" in md.parts or "node_modules" in md.parts:
        continue
    text = md.read_text(encoding="utf-8")
    for raw in sorted(set(link_re.findall(text))):
        link = raw.strip()
        if link.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = unquote(link.split("#", 1)[0].strip("<>"))
        if not target:
            continue
        checked += 1
        path = (md.parent / target).resolve()
        if not path.exists():
            print(f"{md.relative_to(root)}: ссылка не найдена: {link}", file=sys.stderr)
            bad += 1

print(f"docs-paths: проверено {checked} ссылок, ошибок {bad}")
raise SystemExit(1 if bad else 0)
PY
