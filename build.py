#!/usr/bin/env python3
"""Собрать все материалы к лабораторным работам по MS Project из tools/project-management/project.yaml.

    python3 tools/project-management/build.py            # XML-файлы для MS Project + расчёты + отчёт .docx
    python3 tools/project-management/build.py --no-xml   # только расчёты и отчёт (без Java/MPXJ)

Результат — в tools/project-management/out/.

Пакет подключается из исходников (`sys.path.insert` с каталогом скрипта) — штатный
PyPA-паттерн «run from source»: скрипт работает без установки. Не заменять на
обязательный `pip install -e .` — на ВМ команды запускаются прямо из клона.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Печать не должна падать на не-ASCII консолях (cp1252 и пр.) — см. T34.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
# run-from-source: каталог скрипта в начало sys.path (PyPA; см. docstring).
sys.path.insert(0, str(HERE))

from pm import analysis, model  # noqa: E402
from pm import paths  # noqa: E402  — единый источник путей и имён (T07)

OUT = paths.OUT

# (имя файла, описание, параметры msproject.build, PERT-веса для длительностей или None)
VARIANTS = [
    (paths.XML_PLAN, "ЛР1–2: календарь, задачи, фазы, вехи, связи, ограничение, крайний срок",
     dict(with_resources=False, with_extras=False), None),
    (paths.XML_FULL, "ЛР3–7, 9: + ресурсы, ставки A/B, доступность, назначения, СДР, заметки, "
     "гиперссылки, настраиваемые поля, коды структуры", dict(), None),
    (paths.XML_FULL_SAFE, "Запасной вариант 02 без настраиваемых полей и кодов структуры "
     "(если основной файл не откроется)", dict(with_extras=False), None),
    (paths.XML_PERT_IN, "ЛР8: три оценки длительности в полях Длительность1–3 (исходные длительности)",
     dict(pert_fields=True), None),
    (paths.XML_PERT_OUT, "ЛР8: длительности заменены ожидаемыми по PERT (веса 1-4-1) — для сравнения",
     dict(pert_fields=True, title_suffix=" (PERT 1-4-1)"), (1, 4, 1)),
]


def build_xml(project: model.Project, out: Path = OUT) -> list[tuple[str, str]]:
    """Собрать все XML-варианты плана (VARIANTS) в каталог out.

    Варианты с PERT-весами получают копию проекта с подменёнными
    длительностями; переданный project не мутируется.

    Returns:
        Пары (имя файла, описание) — их же печатает раздел «Файлы для MS Project».
    """
    # Импорт внутри функции, а не в шапке файла: msproject тянет JPype/MPXJ,
    # поэтому режим --no-xml (расчёты и отчёт) вообще не грузит Java-стек.
    from pm import msproject as ms
    made = []
    for name, desc, kwargs, weights in VARIANTS:
        p = model.with_pert_durations(project, weights) if weights else project
        f = ms.build(p, **kwargs)
        ms.write(f, out / name, p)
        made.append((name, desc))
    return made


def expected(project: model.Project) -> dict:
    """Эталонные значения для сверки с MS Project на ВМ (tools/project-management/vm/ms_project_labs.py verify).

    Задачи ключуются именами, а не внутренними ключами модели: у скрипта на
    ВМ есть только то, что видно в самом MS Project, а имена задач уникальны
    (инвариант model.Project).
    """
    from pm import cpm, report
    s, cal = cpm.schedule(project)
    phases, total, by_code, by_res, costs = analysis.cost_summary(project)
    _, fins = analysis.pert_table(project)
    return {
        "project_start": project.start.isoformat(),
        "project_finish": analysis.finish_of(project).isoformat(timespec="minutes"),
        "total_cost_A": total,
        "total_cost_B": analysis.cost_summary(project, "B")[1],
        "tasks": {t.name: {
            "wbs": t.wbs,
            "start": (cal.finish_dt(s[t.key].es) if t.milestone else cal.start_dt(s[t.key].es)).isoformat(timespec="minutes"),
            "finish": cal.finish_dt(s[t.key].ef).isoformat(timespec="minutes"),
            "critical": (not t.summary) and s[t.key].slack <= 1e-9,
            "cost": costs[t.key]["total"],
            "fixed_cost": t.fixed_cost,
        } for t in project.tasks},
        "overallocated": sorted(project.resource(k).name for k in cpm.overallocations(project, s, cal)),
        "pert_finish": {"-".join(map(str, w)) if isinstance(w, tuple) else w: d.isoformat(timespec="minutes")
                        for w, d in fins.items()},
        "crash": [{"label": lab, "finish": d.isoformat(timespec="minutes")}
                  for lab, d, _ in analysis.crash_scenarios(project)],
        "shots": report.shots(project),
    }


def main() -> int:
    """Точка входа: разобрать аргументы и собрать out/ (XML, expected.json, analysis.md, .docx).

    Returns:
        Код завершения для SystemExit (0 — успех).
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-xml", action="store_true", help="не генерировать XML (не нужна Java)")
    ap.add_argument("--no-docx", action="store_true", help="не генерировать отчёт .docx")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"каталог вывода (по умолчанию {OUT}; для теста детерминизма)", metavar="DIR")
    args = ap.parse_args()

    out = args.out or OUT
    project = model.load(paths.PROJECT_YAML)
    out.mkdir(exist_ok=True)
    made = [] if args.no_xml else build_xml(project, out)

    import json
    # newline="\n": на Windows write_text кладёт CRLF, а .gitattributes требует LF →
    # каждый прогон иначе помечает файл изменённым в git status (шум). См. T34.
    (out / paths.EXPECTED_JSON).write_text(json.dumps(expected(project), ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"✓ {out / paths.EXPECTED_JSON}")

    from pm import report
    md = report.markdown(project, made)
    (out / paths.ANALYSIS_MD).write_text(md, encoding="utf-8", newline="\n")
    print(f"✓ {out / paths.ANALYSIS_MD}")
    if not args.no_docx:
        path = report.docx(project, out / paths.REPORT_DOCX)
        print(f"✓ {path}")
    for name, _ in made:
        print(f"✓ {out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
