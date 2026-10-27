#!/usr/bin/env python3
"""Собрать все материалы к лабораторным работам по MS Project из project.yaml.

    python3 build.py            # XML-файлы для MS Project + расчёты + отчёт .docx
    python3 build.py --no-xml   # только расчёты и отчёт (без Java/MPXJ)
    python3 build.py --full     # то же + .mpp + 22 скриншота + финальный отчёт
                                #   (Windows + MS Project; шаги COM последовательны)

Результат — в out/. Режим --full дополнительно прогоняет automation/ и кладёт
готовый (со скриншотами) отчёт поверх шаблона out/ms-project-labs-report.docx.

Пакет подключается из исходников (`sys.path.insert` с `src/`) — штатный
PyPA-паттерн «run from source»: скрипт работает без установки. Не заменять на
обязательный `pip install -e .` — на ВМ команды запускаются прямо из клона.
"""
from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

# Печать не должна падать на не-ASCII консолях (cp1252 и пр.) — см. T-034.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
# run-from-source: src/ в начало sys.path (PyPA; см. docstring).
sys.path.insert(0, str(HERE / "src"))

from pm import analysis, model  # noqa: E402
from pm import paths  # noqa: E402  — единый источник путей и имён (T-007)

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
    """Эталонные значения для сверки с MS Project (tests/test_pm.py: test_full_xml_roundtrip_fields).

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


def _write_calculations(project: model.Project, out: Path, no_docx: bool,
                        made: list[tuple[str, str]] | None) -> None:
    """expected.json + analysis.md (+ шаблон .docx). Чистый Python, без Java/COM.

    Запускается параллельно с build_xml: не читает out/*.xml и не трогает JVM.
    `made` — список XML-вариантов для раздела «Файлы для MS Project» (можно None).
    """
    import json
    from pm import report
    # newline="\n": на Windows write_text кладёт CRLF, а .gitattributes требует LF →
    # каждый прогон иначе помечает файл изменённым в git status (шум). См. T-034.
    (out / paths.EXPECTED_JSON).write_text(json.dumps(expected(project), ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"✓ {out / paths.EXPECTED_JSON}")
    md = report.markdown(project, made)
    (out / paths.ANALYSIS_MD).write_text(md, encoding="utf-8", newline="\n")
    print(f"✓ {out / paths.ANALYSIS_MD}")
    if not no_docx:
        path = report.docx(project, out / paths.REPORT_DOCX)
        print(f"✓ {path}")


def run_full_pipeline(out: Path) -> int:
    """Конвейер COM: .mpp → 22 скриншота → вставка в отчёт → готовый .docx в out/.

    Windows + установленный MS Project (автоматизация automation/). Шаги
    последовательны: один экземпляр WINPROJ.exe на машине, параллельный COM
    конфликтует. Возвращает код завершения (0 — успех, 1 — любой шаг упал).
    """
    import subprocess
    steps = [
        ("XML→.mpp", [sys.executable, "scripts/xml_to_mpp.py"]),
        ("скриншоты ЛР1–9", [sys.executable, "-m", "automation.ms_project_ui", "shots"]),
        ("вставка скриншотов в отчёт", [sys.executable, "-m", "automation.fill_report",
                                        "--dst", str(out / paths.REPORT_DOCX)]),
    ]
    for label, cmd in steps:
        print(f"\n— {label}: {' '.join(cmd[1:])}", flush=True)
        try:
            r = subprocess.run(cmd, cwd=HERE, timeout=900,
                               # Не тащим stderr родителя: иначе cp1252-консоль
                               # ломает кириллицу в трейсбеках подчинённого.
                               env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.TimeoutExpired:
            print(f"✗ шаг «{label}» завис (>15 мин) — прерван")
            return 1
        if r.returncode != 0:
            print(f"✗ шаг «{label}» упал (код {r.returncode}) — см. сообщения выше")
            return 1
    ready = out / paths.REPORT_DOCX
    size = ready.stat().st_size if ready.exists() else 0
    print(f"\n✓ полный конвейер: {ready} ({size} bytes)")
    return 0


def main() -> int:
    """Точка входа: разобрать аргументы и собрать out/ (XML, expected.json, analysis.md, .docx).

    Returns:
        Код завершения для SystemExit (0 — успех).
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-xml", action="store_true", help="не генерировать XML (не нужна Java)")
    ap.add_argument("--no-docx", action="store_true", help="не генерировать отчёт .docx")
    ap.add_argument("--full", action="store_true",
                    help="после сборки: .mpp + скриншоты + финальный отчёт (Windows + MS Project)")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"каталог вывода (по умолчанию {OUT}; для теста детерминизма)", metavar="DIR")
    args = ap.parse_args()

    out = args.out or OUT
    project = model.load(paths.PROJECT_YAML)
    out.mkdir(exist_ok=True)

    if args.no_xml:
        _write_calculations(project, out, args.no_docx, made=None)
    else:
        # Список XML-вариантов известен статически — не ждём build_xml, чтобы
        # analysis.md сразу ушёл с разделом «Файлы для MS Project».
        made_static = [(name, desc) for name, desc, _, _ in VARIANTS]
        # Параллельно: XML (JVM) в фоне ‖ расчёты/отчёт в главном потоке.
        # JVM поднимаем в главном ДО старта фонового потока: JPype не
        # потокобезопасен при старте из worker-потока.
        from pm import msproject as ms
        ms.jvm()
        err: list[BaseException] = []

        def _xml():
            try:
                build_xml(project, out)
            except BaseException as e:  # noqa: BLE001 — пробрасываем в main
                err.append(e)

        t = threading.Thread(target=_xml, name="build-xml", daemon=True)
        t.start()
        _write_calculations(project, out, args.no_docx, made=made_static)
        t.join()
        if err:
            raise err[0]
        for name, _ in made_static:
            print(f"✓ {out / name}")

    if args.full:
        if args.out:
            print("предупреждение: --full всегда работает с каталогом out/ проекта, --out игнорируется")
        return run_full_pipeline(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
