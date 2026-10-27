#!/usr/bin/env python3
"""Манифест SHA-256 для бинарных артефактов (.mpp, .docx, .xml).

    python vm/hash_artifacts.py            # перегенерировать
    python vm/hash_artifacts.py --check    # только проверить, exit 1 при расхождении

Формат — как у GNU ``sha256sum``: ``<hash><два пробела><путь от корня репозитория>``,
UTF-8 без BOM, перевод строк LF. Пути относительные, поэтому манифест переносим
между машинами и проверяется командой ``sha256sum -c`` из корня.

Почему отдельный файл, а не инлайн в PowerShell: PowerShell 5.1 искажает
кириллицу и спецсимволы в here-string, переданном в ``py -c``.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

from pm import paths  # noqa: E402

OUT = paths.RESULTS / "checksums.sha256"


def entries() -> list[tuple[str, str]]:
    """Все канонические бинарные артефакты: out/*.mpp, results/*.mpp, submission/*.mpp."""
    files: list[Path] = []
    files += sorted(paths.OUT.glob("*.mpp"))
    files += sorted(paths.RESULTS.glob("*.mpp"))
    files += sorted(paths.SUBMISSION_DIR.glob("*.mpp"))
    return [(p.relative_to(ROOT).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in files]


def write() -> int:
    ents = entries()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes("".join(f"{h}  {n}\n" for n, h in ents).encode("utf-8"))
    print(f"checksums.sha256: {len(ents)} записей (UTF-8 без BOM, LF) -> {OUT}")
    return 0


def check() -> int:
    if not OUT.exists():
        print(f"нет {OUT} — запусти без --check", file=sys.stderr)
        return 1
    want: dict[str, str] = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, n = line.split(None, 1)
            want[n.lstrip("*")] = h
    have = dict(entries())
    bad = sorted(set(want) ^ set(have)) + sorted(n for n in set(want) & set(have)
                                                 if want[n] != have[n])
    if bad:
        print("расхождения манифеста с диском:", file=sys.stderr)
        for n in bad:
            print(f"  {n}", file=sys.stderr)
        return 1
    print(f"checksums.sha256: все {len(have)} записей совпадают")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="не перезаписывать, а проверить манифест")
    a = ap.parse_args()
    return check() if a.check else write()


if __name__ == "__main__":
    raise SystemExit(main())
