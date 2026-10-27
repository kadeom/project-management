#!/usr/bin/env python3
"""Собрать весь учебный комплект: ЛР, СРС, два ДЗ и методические указания.

    python build_all.py              # без XML/Java: .md, .docx
    python build_all.py --xml        # + XML MSPDI (нужна Java 8+)
    python build_all.py --full       # + .mpp, скриншоты, финальный отчёт (Windows + MS Project)

Каждый шаг — отдельный процесс, чтобы падение одного генератора не прятало
остальные. Код возврата 1, если упал хотя бы один шаг.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent


def run(label: str, args: list[str]) -> bool:
    print(f"\n==> {label}: {' '.join(args)}", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, *args], cwd=HERE, env=env)
    if r.returncode:
        print(f"✗ {label}: код {r.returncode}", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xml", action="store_true", help="собрать XML (нужна Java)")
    ap.add_argument("--no-xml", action="store_true", help="явно без XML (по умолчанию и так без XML)")
    ap.add_argument("--full", action="store_true", help=".mpp + скриншоты (Windows + MS Project)")
    ap.add_argument("--skip-labs", action="store_true")
    ap.add_argument("--skip-infosec", action="store_true")
    ap.add_argument("--skip-siw", action="store_true", help="не собирать СРС (SIW)")
    ap.add_argument("--skip-guidelines", action="store_true")
    ap.add_argument("--skip-artifacts", action="store_true", help="не собирать паспорт проекта")
    args = ap.parse_args()

    no_xml = args.no_xml or not (args.xml or args.full)
    ok = True
    if not args.skip_labs:
        lab_args = ["build.py"]
        if no_xml:
            lab_args.append("--no-xml")
        if args.full:
            lab_args.append("--full")
        ok &= run("лабораторные работы", lab_args)
    if not args.skip_infosec:
        inf_args = ["build_infosec.py"]
        if args.full:
            inf_args.append("--full")
        elif no_xml:
            inf_args.append("--no-xml")
        ok &= run("дополнительные задания 10/12", inf_args)
    if not args.skip_siw:
        ok &= run("СРС (SIW)", ["build_siw.py"])
    if not args.skip_guidelines:
        ok &= run("методические указания", ["build_guidelines.py"])
    if not args.skip_artifacts:
        ok &= run("паспорт проекта", ["build_artifacts.py"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
