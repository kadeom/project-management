#!/usr/bin/env python3
"""Собрать отчёт по самостоятельной работе студента (СРС).

    python build_siw.py
    python build_siw.py --no-docx

Источник заданий — ``siw/siw.yaml``, числа — ``project.yaml``. Результат:
``out/siw-report.md`` и ``out/siw-report.docx``. Скриншоты вставляются
позже командой ``python -m automation.fill_report`` (метки siw_lrN_KK).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))          # run-from-source

from pm import model, paths, report_siw  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=paths.SIW_YAML, help="siw.yaml")
    ap.add_argument("--out", type=Path, default=paths.OUT, help="каталог вывода")
    ap.add_argument("--no-docx", action="store_true", help="только Markdown, без .docx")
    args = ap.parse_args()

    project = model.load(paths.PROJECT_YAML)
    data = report_siw.load(args.src)
    args.out.mkdir(parents=True, exist_ok=True)

    md_path = args.out / paths.SIW_REPORT_MD
    md_path.write_text(report_siw.markdown(project, data), encoding="utf-8", newline="\n")
    print(f"✓ {md_path}")

    if not args.no_docx:
        docx_path = report_siw.docx(project, data, args.out / paths.SIW_REPORT_DOCX)
        print(f"✓ {docx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
