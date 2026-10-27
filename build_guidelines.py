#!/usr/bin/env python3
"""Собрать методические указания из Markdown в .docx.

    python build_guidelines.py
    python build_guidelines.py --src docs/guidelines/methodical-guidelines.md

Связанный файл — ``docs/guidelines/methodical-guidelines.md``: заголовки,
таблицы, списки и front matter одновременно читаются человеком и служат
источником для ``out/methodical-guidelines.docx``. Готовый .docx не правят
руками: правка идёт в Markdown, затем повторная сборка.
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
    ap.add_argument("--src", type=Path, default=paths.GUIDELINES_MD)
    ap.add_argument("--dst", type=Path, default=paths.OUT / paths.GUIDELINES_DOCX)
    ap.add_argument("--no-toc", action="store_true", help="без поля оглавления")
    args = ap.parse_args()

    meta, body = md_docx.load_markdown(args.src)
    blocks = md_docx.parse(body)
    path = md_docx.render_docx(blocks, args.dst, meta=meta, title_page=True, toc=not args.no_toc)
    print(f"✓ {path} ({len(blocks)} блоков)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
