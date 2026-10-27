#!/usr/bin/env python3
"""Сверить расчёт MS Project с эталоном ``out/expected.json``.

    python vm/verify.py
    python vm/verify.py --json automation/results/verify.json

Запускать на Windows с установленным MS Project. Скрипт только читает файлы
(``ReadOnly=True``) и пишет отчёт; расхождения не «подгоняются»: истина —
MS Project, причина фиксируется в ``automation/results/NOTES.md``.

Проверяются: окончание проекта, стоимость, даты/критичность/стоимость задач,
перегруженные ресурсы и окончание PERT 1-4-1. Сценарии сокращения ЛР9
сравниваются отдельно, потому что требуют изменения плана.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
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


def iso(value) -> str:
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(value, dt.date):
        return value.strftime("%Y-%m-%dT00:00")
    return str(value)


def open_mpp(app, stem: str):
    for folder in (paths.RESULTS, paths.OUT):
        p = folder / f"{stem}.mpp"
        if p.exists():
            app.FileOpenEx(Name=str(p), ReadOnly=True)
            return app.ActiveProject
    raise FileNotFoundError(f"нет {stem}.mpp в out/ или automation/results/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path, default=paths.RESULTS / "verify.json")
    args = ap.parse_args()

    expected = json.loads((paths.OUT / paths.EXPECTED_JSON).read_text(encoding="utf-8"))
    import win32com.client

    app = win32com.client.Dispatch("MSProject.Application")
    app.Visible = False
    app.DisplayAlerts = False
    rep: dict = {"tasks": [], "summary": {}, "warnings": []}
    try:
        project = open_mpp(app, Path(paths.XML_FULL).stem)
        summary = project.ProjectSummaryTask
        rep["summary"] = {
            "finish": {"project": iso(summary.Finish), "expected": expected["project_finish"]},
            "cost": {"project": float(summary.Cost), "expected": float(expected["total_cost_A"])},
        }

        for name, want in expected["tasks"].items():
            task = next((t for t in project.Tasks if t is not None and t.Name == name), None)
            if task is None:
                rep["tasks"].append({"name": name, "error": "задача не найдена"})
                continue
            row: dict = {"wbs": want["wbs"], "name": name}
            for field, got in (("start", iso(task.Start)), ("finish", iso(task.Finish))):
                if got != want[field]:
                    row[field] = {"project": got, "expected": want[field]}
            if not task.Summary and bool(task.Critical) != bool(want["critical"]):
                row["critical"] = {"project": bool(task.Critical), "expected": bool(want["critical"])}
            if abs(float(task.Cost) - float(want["cost"])) > 1:
                row["cost"] = {"project": float(task.Cost), "expected": float(want["cost"])}
            if abs(float(task.FixedCost) - float(want["fixed_cost"])) > 0.01:
                row["fixed_cost"] = {"project": float(task.FixedCost), "expected": float(want["fixed_cost"])}
            if len(row) > 2:
                rep["tasks"].append(row)

        over = sorted(r.Name for r in project.Resources if r is not None and r.Overallocated)
        rep["overallocated"] = {"project": over, "expected": expected["overallocated"]}

        app.FileCloseEx(0)  # pjDoNotSave
        pert = open_mpp(app, Path(paths.XML_PERT_OUT).stem)
        rep["pert_1-4-1_finish"] = {
            "project": iso(pert.ProjectSummaryTask.Finish),
            "expected": expected["pert_finish"].get("1-4-1"),
        }
        rep["warnings"].append("Сценарии ЛР9 требуют изменения плана и здесь не проверяются.")
        rep["ok"] = (
            not rep["tasks"]
            and rep["summary"]["finish"]["project"] == rep["summary"]["finish"]["expected"]
            and abs(rep["summary"]["cost"]["project"] - rep["summary"]["cost"]["expected"]) <= 1
            and rep["overallocated"]["project"] == rep["overallocated"]["expected"]
            and rep["pert_1-4-1_finish"]["project"] == rep["pert_1-4-1_finish"]["expected"]
        )
    finally:
        app.Quit()

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("verify:", "OK" if rep["ok"] else f"расхождения → {args.json}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
