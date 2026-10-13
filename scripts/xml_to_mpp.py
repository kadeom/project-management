"""Конвертация out/*.xml → out/*.mpp через COM-автоматизацию MS Project.

XML (MSPDI) — источник истины и то, что генерирует build.py без MS Project.
MPP — проприетарный бинарь, создаётся только самим MS Project; скрипт открывает
XML и сохраняет как .mpp, чтобы студентам не нужно было делать импорт вручную.

Запуск (нужен установленный MS Project, Windows):
    py -3 scripts/xml_to_mpp.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
XML_VARIANTS = [
    "01_plan_LR1-2.xml",
    "02_full_LR3-7_9.xml",
    "02_full_safe.xml",
    "03_pert_input_LR8.xml",
    "04_pert_result_LR8.xml",
]


def convert() -> int:
    app = win32com.client.Dispatch("MSProject.Application")
    app.Visible = False
    app.DisplayAlerts = False
    made = []
    try:
        for name in XML_VARIANTS:
            xml = OUT / name
            mpp = OUT / (xml.stem + ".mpp")
            if not xml.exists():
                print(f"skip (нет XML): {xml.name}")
                continue
            app.FileOpen(str(xml))
            # pjNative = 0 → сохранить в родном формате .mpp
            app.FileSaveAs(str(mpp), Format=0)
            app.FileClose(0)  # pjDoNotSave — файл уже сохранён как .mpp
            made.append(mpp.name)
            print(f"ok: {name} -> {mpp.name} ({mpp.stat().st_size} bytes)")
    finally:
        app.Quit()
    print(f"\nСоздано {len(made)} .mpp в {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(convert())
