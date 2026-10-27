#!/usr/bin/env python3
"""Собрать паспорт проекта (устав, stakeholders, WBS, RACI, риски и др.).

    python build_artifacts.py
    python build_artifacts.py --src docs/artifacts/example-conference-2026.md

Связанный файл — ``docs/artifacts/example-conference-2026.md``: один
Markdown-источник, из которого получается готовый ``out/project-artifacts.docx``.
Шаблоны для собственного проекта — в ``docs/artifacts/templates/``.
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
sys.path.insert(0, str(HERE / "src"))

from pm import md_docx, paths  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=paths.ARTIFACTS_MD)
    ap.add_argument("--dst", type=Path, default=paths.OUT / paths.ARTIFACTS_DOCX)
    args = ap.parse_args()

    meta, body = md_docx.load_markdown(args.src)
    path = md_docx.render_docx(md_docx.parse(body), args.dst, meta=meta)
    print(f"✓ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
