#!/usr/bin/env python3
"""Собрать практическую работу (дополнительное задание) по обоим вариантам СЗИ.

    py build_infosec.py            # .docx + .md в папки вариантов + XML в out/
    py build_infosec.py --no-xml   # только .docx/.md (без Java/MPXJ)
    py build_infosec.py --full     # + .mpp + 10 скриншотов v12_*/v10_* + вставка в .docx

Варианты:
    additional-assignment/01-pam/    (вар. 12, PAM)     → out/infosec_v12_full.xml
    additional-assignment/02-dlp-siem/ (вар. 10, DLP+SIEM) → out/infosec_v10_full.xml

Документ каждого варианта (additional-assignment-variant-*.docx) собирается src/pm/report_infosec.py:
титул, содержание (поле TOC), задания 1–7 методички, расчётная часть (сроки,
смета в сомах с импортными позициями в USD, перегрузки), выводы, источники.

Пакет подключается из исходников (`sys.path.insert`) — штатный PyPA-паттерн
«run from source»: скрипт работает без установки.
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

from pm import model, paths, report_infosec  # noqa: E402

# (каталог варианта, префикс скриншотов/полей, имя XML в out/, имя документа)
VARIANTS = [
    ("01-pam", "v12", paths.XML_INFOSEC_V12, "additional-assignment-variant-12-pam.docx"),
    ("02-dlp-siem", "v10", paths.XML_INFOSEC_V10, "additional-assignment-variant-10-dlp-siem.docx"),
]


def variant_dir(name: str) -> Path:
    return HERE / "additional-assignment" / name


def build_docs(no_docx: bool = False) -> list[Path]:
    """Документы и Markdown-вычитка каждого варианта в его каталоге."""
    made = []
    for name, prefix, _, doc_name in VARIANTS:
        d = variant_dir(name)
        project = model.load(d / "project.yaml")
        data = report_infosec.load_yaml(d / "project.yaml")
        md = d / doc_name.replace(".docx", ".md")
        md.write_text(report_infosec.markdown(report_infosec.blocks(project, data, prefix)),
                      encoding="utf-8", newline="\n")
        print(f"✓ {md}")
        made.append(md)
        if not no_docx:
            out = report_infosec.docx(project, data, d / doc_name, prefix)
            print(f"✓ {out}")
            made.append(out)
    return made


def build_xmls() -> list[Path]:
    """XML MSPDI каждого варианта в out/ (нужна Java/MPXJ)."""
    from pm import msproject as ms
    made = []
    for name, _, xml_name, _ in VARIANTS:
        project = model.load(variant_dir(name) / "project.yaml")
        ms.jvm()
        f = ms.build(project, with_resources=True, with_extras=True)
        path = paths.OUT / xml_name
        ms.write(f, path, project)
        print(f"✓ {path}")
        made.append(path)
    return made


def run_full_pipeline() -> int:
    """Конвейер COM: .mpp → 10 скриншотов v12_*/v10_* → вставка в документы .docx."""
    import os
    import subprocess
    shots_only = ",".join(i for p in ("v12", "v10") for i in report_infosec.shot_ids(p))
    steps = [
        ("XML→.mpp", [sys.executable, "scripts/xml_to_mpp.py"]),
        ("скриншоты v12/v10", [sys.executable, "-m", "automation.ms_project_ui",
                               "shots", "--only", shots_only]),
    ]
    for name, _, _, doc_name in VARIANTS:
        src = variant_dir(name) / doc_name
        dst = variant_dir(name) / doc_name.replace(".docx", "-with-screenshots.docx")
        steps.append((f"скриншоты в документ ({name})",
                      [sys.executable, "-m", "automation.fill_report",
                       "--src", str(src), "--dst", str(dst)]))
    for label, cmd in steps:
        print(f"\n— {label}: {' '.join(cmd[1:])}", flush=True)
        try:
            r = subprocess.run(cmd, cwd=HERE, timeout=900,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            print(f"✗ шаг «{label}» завис (>15 мин) — прерван")
            return 1
        if r.returncode != 0:
            print(f"✗ шаг «{label}» упал (код {r.returncode}) — см. сообщения выше")
            return 1
    print("\n✓ полный конвейер ДЗ готов")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-xml", action="store_true", help="не генерировать XML (не нужна Java)")
    ap.add_argument("--no-docx", action="store_true", help="не генерировать .docx (только .md)")
    ap.add_argument("--full", action="store_true",
                    help="после сборки: .mpp + скриншоты + документы со скриншотами "
                         "(Windows + MS Project)")
    a = ap.parse_args()

    paths.OUT.mkdir(exist_ok=True)
    build_docs(no_docx=a.no_docx)
    if not a.no_xml:
        build_xmls()
    if a.full:
        return run_full_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
