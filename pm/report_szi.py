"""Дополнительное задание: практическая работа по планированию проекта внедрения СЗИ.

Формат — практическая работа, а не курсовая: титул, содержание, исходные данные
с понятиями ГОСТ Р ИСО 21500-2023, задания 1–7 методички, расчётная часть (сроки
и критический путь, смета в базовой валюте с импортными позициями в USD,
перегрузки ресурсов), выводы и список источников.

Содержание заданий берётся из блока `report:` project.yaml (модель Project его
не хранит, поэтому YAML читается отдельно), расчёты — pm.analysis/cpm. Скриншоты
имеют ID вида v12_01 / v10_01: снимаются automation.ms_project_ui
(szi_shot_steps), вставляются automation.fill_report (общий SHOT_MARK).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import analysis as a
from . import currency as fx_mod
from .model import Project

# Кейс методички (раздел 3) — общ для вариантов 10 и 12.
CASE = ("МФО «Вектор-Финанс»: 600 сотрудников, головной офис и 3 филиала, "
        "~120 серверов, 15 администраторов и подрядчиков с привилегированным "
        "доступом, ИБ-подразделение — 4 человека. После инцидента с утечкой "
        "персональных данных через почту руководство выделило бюджет и срок "
        "на внедрение СЗИ.")

WORK_GOAL = ("Сформировать модель проекта внедрения СЗИ: устав с измеримой целью, "
             "реестр заинтересованных сторон и план коммуникаций, WBS с "
             "календарным планом и вехами, план пилота, реестр рисков с матрицей "
             "5×5, метрики и порядок передачи в эксплуатацию, смету в базовой "
             "валюте с учётом импортных позиций в USD; проверить расчёт в MS Project.")

# Определения — компактно по ГОСТ Р ИСО 21500-2023 (п. 5 «Основные понятия»);
# формулировки сокращены, терминология сохранена.
DEFS = [
    ("Проект", "уникальный процесс, состоящий из серии координированных и "
     "управляемых задач с датами начала и окончания, направленный на достижение "
     "определённой цели"),
    ("Управление проектами", "применение знаний, умений, инструментов и методов "
     "к деятельности проекта для удовлетворения его требований"),
    ("Результат", "уникальный совокупный продукт проекта: здесь — работающая СЗИ, "
     "процессы и регламенты, принятые заказчиком"),
    ("Ограничения", "сдерживающие факторы проекта: срок (9 месяцев), стоимость "
     "(бюджет), ресурсы (штат ИБ 4 чел.), качество и требования регуляторов"),
    ("Веха", "контрольная точка проекта для измерения прогресса — в плане это "
     "задачи с нулевой длительностью (утверждение устава, приёмка пилота, ввод "
     "в эксплуатацию, закрытие)"),
]

# Оформление источников — по ГОСТ Р 7.0.100-2018 (б.и., с.).
SOURCES = [
    "ГОСТ Р ИСО 21500-2023. Управление проектами, программы и портфели проектов. "
    "Контекст организации. — М.: Стандартинформ, 2023. — Введён с 01.06.2024 "
    "(приказ Росстандарта от 30.10.2023 № 1293-ст; идентичен ISO 21500:2021).",
    "ГОСТ Р 7.0.100-2018. Библиографическая запись. Библиографическое описание. "
    "Общие требования и правила составления. — М.: Стандартинформ, 2018. — "
    "Введён с 01.07.2019 (приказ Росстандарта от 03.12.2018 № 1050-ст).",
    "ГОСТ Р 57580.1-2017. Безопасность финансовых (банковских) операций. Меры "
    "защиты информации. Часть 1. Общие меры защиты информации. — М.: "
    "Стандартинформ, 2017. — Введён с 01.01.2018.",
    "О персиональных данных : федеральный закон от 27.07.2006 № 152-ФЗ (в ред. "
    "действующих редакций). — URL: http://publication.pravo.gov.ru (дата "
    "обращения: 14.10.2026).",
    "Об утверждении состава и содержания организационных и технических мер по "
    "защите персональных данных при их обработке в персональных данных системах : "
    "приказ ФСТЭК России от 18.02.2013 № 21. — Действует.",
    "ISO/IEC 27001:2022. Information security, cybersecurity and privacy "
    "protection — Information security management systems — Requirements. — "
    "Geneva: ISO/IEC, 2022 (приложение A, пп. A.5.7, A.5.8, A.8.2, A.8.12, "
    "A.8.15, A.8.16).",
    "Computer Security Incident Handling Guide : NIST Special Publication "
    "800-61 Revision 3. — Gaithersburg: NIST, 2025 (апрель).",
    "MITRE ATT&CK Enterprise. — The MITRE Corporation. — URL: "
    "https://attack.mitre.org (дата обращения: 14.10.2026).",
    "Методические указания «Планирование проекта внедрения систем защиты "
    "информации» : по дисциплине «Управление проектами в информационной "
    "безопасности» (магистратура). — Локальный документ вуза, 2026.",
    "Курсы валют Национального банка Кыргызской Республики (XML daily). — URL: "
    "https://www.nbkr.kg/XML/daily.xml (дата обращения: 15.10.2026).",
]

SHOT_MARK = "[ Вставьте скриншот {id}: {caption} ]"


def load_yaml(path: str | Path) -> dict:
    """Прочитать project.yaml как обычный словарь (блоки report/fx/cost_basis)."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _kgs(x: float) -> str:
    return a.money(x, "сом")


def _usd(x: float) -> str:
    return f"{x:,.2f} $".replace(",", " ").replace(".", ",")


def _num(x: float) -> str:
    """Число в русской записи: 87.45 → «87,45», 1.0438 → «1,0438»."""
    return f"{x:g}".replace(".", ",")


def _rub(x: float) -> str:
    """Целые с группировкой разрядов: 12000000 → «12 000 000»."""
    return f"{x:,.0f}".replace(",", " ")


def _plural(n: int, forms: tuple[str, str, str]) -> str:
    """Склонение существительного при числе: (работа, работы, работ)."""
    if n % 10 == 1 and n % 100 != 11:
        w = forms[0]
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        w = forms[1]
    else:
        w = forms[2]
    return f"{n} {w}"


# ---------- содержание ----------

def blocks(project: Project, data: dict, prefix: str) -> list[tuple]:
    """Все блоки практической работы (см. модуль report: список кортежей)."""
    B: list[tuple] = []
    meta = project.meta
    rep = data["report"]
    fx = fx_mod.from_yaml(data)
    rows = a.schedule_rows(project)
    finish = a.finish_of(project)
    leaves = project.leaf_tasks
    milestones = [t for t in leaves if t.milestone]
    works = [t for t in leaves if not t.milestone]
    phases, total, by_code, _, _ = a.cost_summary(project)
    _, total_b, _, _, _ = a.cost_summary(project, "B")
    budget_kgs = meta.get("budget_rub", 0) * (fx.rub if fx else 1.0)

    # ---------- 1. Исходные данные ----------
    B += [
        ("h1", "1. Исходные данные и цель работы"),
        ("p", CASE),
        ("p", "Цель работы: " + WORK_GOAL),
        ("h2", "1.1. Исходные данные проекта"),
        ("table", ["Параметр", "Значение"], [
            ["Вариант", f"{meta['variant']} — {meta['system']} ({meta.get('variant_note', '')})"],
            ["Организация", meta.get("company", "")],
            ["Объект внедрения", meta["name"]],
            ["Срок проекта", f"{project.start:%d.%m.%Y} – {finish:%d.%m.%Y} "
                             f"(дедлайны вех — {max((t.deadline for t in leaves if t.deadline), default='—'):%d.%m.%Y})"]
            if any(t.deadline for t in leaves) else
            ["Срок проекта", f"{project.start:%d.%m.%Y} – {finish:%d.%m.%Y}"],
            ["Бюджет", f"{_rub(meta.get('budget_rub', 0))} ₽ = {_kgs(budget_kgs)} "
                       f"(курс {_num(fx.rub)} сом/₽, {fx.date:%d.%m.%Y}, {fx.source})" if fx else "—"],
            ["Валюта проекта", f"{meta.get('currency', '')} ({meta.get('currency_code', '')}); "
                               f"импортные позиции — USD по курсу {_num(fx.usd) if fx else 0} сом/USD"],
            ["Объём плана", f"фаз — {sum(t.summary for t in project.tasks)}, работ — {len(works)}, "
                            f"вех — {len(milestones)}, ресурсов — {len(project.resources)}"],
            ["Инструмент расчёта", "project.yaml → CPM-расчёт (pm) → XML MSPDI → MS Project"],
            ["Репозиторий", meta.get("repo", "")],
        ]),
        ("h2", "1.2. Основные понятия (ГОСТ Р ИСО 21500-2023)"),
        *[("li", f"{term} — {text}.") for term, text in DEFS],
        ("h2", "1.3. Специфика системы (вариант)"),
        *[("li", s) for s in rep.get("specifics", [])],
    ]

    # ---------- 2. Устав ----------
    c = rep["task1_charter"]
    B += [
        ("h1", "2. Задание 1. Устав проекта"),
        ("h2", "2.1. Цель проекта"), ("p", c["goal"]),
        ("h2", "2.2. Границы проекта"),
        ("p", "В границы входит:"), *[("li", s) for s in c["scope_in"]],
        ("p", "В границы не входит:"), *[("li", s) for s in c["scope_out"]],
        ("h2", "2.3. Допущения"), *[("li", s) for s in c["assumptions"]],
        ("h2", "2.4. Ограничения"), ("p", c["constraints"]),
        ("h2", "2.5. Критерии приёмки результата"),
        *[("li", s) for s in c["success"]],
        ("h2", "2.6. Роли и полномочия"),
        ("table", ["Роль", "Кто и какие полномочия имеет"], [
            ["Спонсор", c["sponsor"]], ["Руководитель проекта", c["manager"]]]),
    ]

    # ---------- 3. Стейкхолдеры ----------
    st = rep["task2_stakeholders"]
    cm = rep["task2_comms"]
    B += [
        ("h1", "3. Задание 2. Заинтересованные стороны и коммуникации"),
        ("p", f"Реестр содержит {len(st)} сторон (методика: влияние × интерес → "
              "сегментация «управление вовлечением / поддержание удовлетворённости»; "
              "влияние: В — высокое, С — среднее, Н — низкое)."),
        ("table", ["№", "Сторона", "Интерес", "Влияние", "Отношение", "Метод воздействия"],
         [[i, x["name"], x["interest"], x["influence"], x["attitude"], x["action"]]
          for i, x in enumerate(st, start=1)]),
        ("h2", "3.1. План коммуникаций"),
        ("table", ["Кому", "Кто информирует", "Периодичность", "Формат", "Содержание"],
         [[x["who"], x["who_informs"], x["freq"], x["format"], x["content"]] for x in cm]),
    ]

    # ---------- 4. WBS и план ----------
    phase_stats = [(t.wbs, t.name,
                    sum(not project.task(k).milestone for k in t.children),
                    sum(project.task(k).milestone for k in t.children))
                   for t in project.tasks if t.summary]
    B += [
        ("h1", "4. Задание 3. WBS, календарный план и вехи"),
        ("p", f"Структура: {len(phase_stats)} фаз жизненного цикла, детализация «сверху вниз», "
              f"{_plural(len(works), ('работа', 'работы', 'работ'))} и "
              f"{_plural(len(milestones), ('веха', 'вехи', 'вех'))}. Типовой состав фазы — 3–5 работ; "
              "отдельной работой инициации вынесено обоснование сметы и валютная политика."),
        ("table", ["Фаза", "Работ", "Вех"],
         [[n, w, m] for _, n, w, m in phase_stats]),
        ("h2", "4.1. Календарный план (структура проекта)"),
        ("table", ["СДР", "Задача", "Длит.", "Начало", "Окончание", "Предшественники", "Ресурсы"],
         [[("◆ " if r["milestone"] else "") + r["wbs"], r["name"], r["dur"], r["start"],
           r["finish"], r["preds"], r["res"]] for r in rows]),
        ("p", "Вехи плана: " + "; ".join(
            f"{r['wbs']} «{r['name']}» — {r['finish']}" for r in rows if r["milestone"]) + "."),
        ("shot", "Диаграмма Ганта: фазы, задачи и вехи проекта", f"{prefix}_01"),
        ("p", "Критический путь и резерв задач приведены в разделе 9.1; назначения "
              "ресурсов и затраты — в разделах 4.2 и 9.2."),
        ("h2", "4.2. Назначения ресурсов"),
        ("table", ["СДР", "Задача", "Ресурсы"],
         [[r["wbs"], r["name"], r["res"]] for r in rows if r["res"] and not r["summary"]]),
    ]

    # ---------- 5. Пилот ----------
    p4 = rep["task4_pilot"]
    B += [
        ("h1", "5. Задание 4. План пилота"),
        ("h2", "5.1. Что проверяем"),
        ("p", f"Контур: {p4['group']}."),
        ("p", f"Почему этот контур: {p4['why']}."),
        ("p", f"Продолжительность: {p4['duration']}."),
        ("h2", "5.2. Ожидаемые результаты"), *[("li", s) for s in p4["results"]],
        ("h2", "5.3. Критерии приёмки"), *[("li", s) for s in p4["acceptance"]],
        ("h2", "5.4. Решение по результатам пилота"), ("p", p4["decision"]),
    ]

    # ---------- 6. Риски ----------
    risks = rep["task5_risks"]
    top3 = sorted(enumerate(risks, start=1),
                  key=lambda ir: -(ir[1]["p"] * ir[1]["i"]))[:3]
    B += [
        ("h1", "6. Задание 5. Управление рисками"),
        ("p", f"В реестре {_plural(len(risks), ('риск', 'риска', 'рисков'))}. "
              "Оценка: вероятность (В) и влияние (Вл) — "
              "шкала 1–5, ожидаемое значение = В × Вл (1–25); реагирование — "
              "избегание, снижение, передача или принятие; владелец отвечает за "
              "меру. Контроль — на недельных встречах проектной группы."),
        ("table", ["№", "Риск", "В", "Вл", "Ожидание", "Реагирование", "Владелец"],
         [[i, x["name"], x["p"], x["i"], x["p"] * x["i"], x["response"], x["owner"]]
          for i, x in enumerate(risks, start=1)]),
        ("h2", "6.1. Матрица рисков 5×5 (влияние × вероятность)"),
        _risk_matrix(risks),
        ("h2", "6.2. Топ-3 риска по ожидаемому значению"),
        *[("li", f"№{i} «{x['name']}» — {x['p'] * x['i']}; владелец: {x['owner']}.")
          for i, x in top3],
    ]

    # ---------- 7. Метрики ----------
    B += [
        ("h1", "7. Задание 6. Метрики и передача в эксплуатацию"),
        ("table", ["Метрика", "Целевое значение", "Способ измерения", "Владелец"],
         [[x["name"], x["target"], x["method"], x["owner"]] for x in rep["task6_metrics"]]),
        ("h2", "7.1. Порядок передачи в эксплуатацию"),
        ("p", rep["handover"]),
    ]

    # ---------- 8. Валидация ----------
    B += [
        ("h1", "8. Задание 7. Оценка соответствия официальным документам"),
        ("p", "Каждое проектное решение опирается на действующий документ; "
              "ссылки на утратившие силу акты (приказ ФСТЭК № 17) исключены "
              "и приведены только с пометкой об актуализации."),
        ("table", ["Решение по проекту", "Официальный документ"],
         [[x["decision"], x["doc"]] for x in rep["validation"]]),
    ]

    # ---------- 9. Расчётная часть ----------
    crit = [r for r in rows if r["critical"]]
    over = a.overalloc_summary(project)
    B += [
        ("h1", "9. Расчётная часть"),
        ("h2", "9.1. Сроки и критический путь"),
        ("p", f"Расчётное окончание — {finish:%d.%m.%Y %H:%M}; работ — {len(works)}, "
              f"вех — {len(milestones)}, критических задач — {len(crit)}. Длительности "
              "считаются PERT (1-4-1) в рабочих днях, календарь — пятидневка 8 ч с "
              "исключениями календаря."),
        ("table", ["СДР", "Критическая задача", "Длит.", "Начало", "Окончание"],
         [[r["wbs"], r["name"], r["dur"], r["start"], r["finish"]] for r in crit]),
        _deadline_note(project),
        ("shot", "Критический путь (Формат → Критические задачи)", f"{prefix}_02"),
        ("h2", "9.2. Смета: базовая валюта и импортные позиции"),
        *_cost_section(project, data, phases, total, total_b, budget_kgs, fx, by_code),
        ("shot", "Таблица «Затраты» в MS Project", f"{prefix}_03"),
        ("h2", "9.3. Перегрузки ресурсов и выравнивание"),
        ("p", "Превышение доступности рассчитано по дням (назначенные часы vs "
              "доступные с учётом таблицы доступности):"),
        ("table", ["Ресурс", "Дней с превышением", "Пик", "Задачи-конфликты", "Периоды"],
         [[o["res"], o["days"],
           "∞ (доступность 0 %)" if o["peak"] == float("inf") else f"{o['peak'] * 100:.0f}%",
           ", ".join(o["tasks"]),
           "; ".join(f"{p[0]:%d.%m}–{p[1]:%d.%m}: {p[2]:g} ч из {p[3]:g}" for p in o["periods"])]
          for o in over] or [["—", 0, "—", "—", "перегрузок нет"]]),
        ("p", "Способы устранения: выравнивание в MS Project (Ресурс → Параметры "
              "выравнивания, «день за днём») с ограничением «только в пределах "
              "резерва», перенос задач с резервом, распределение нагрузки на "
              "подрядчика и сверхурочные в дни пика. Выравнивание может сдвинуть "
              "окончание — сверяется с дедлайнами вех (раздел 9.1)."),
        ("shot", "Лист ресурсов: ресурсы с превышением доступности", f"{prefix}_04"),
        ("shot", "Использование ресурсов: профиль загрузки", f"{prefix}_05"),
    ]

    # ---------- 10–11 ----------
    B += [
        ("h1", "10. Выводы"),
        ("p", f"План: окончание {finish:%d.%m.%Y}, стоимость по таблице A — "
              f"{_kgs(total)} при бюджете {_kgs(budget_kgs)} "
              f"(резерв {100 * (budget_kgs - total) / budget_kgs:.1f} %); "
              f"таблица B — {_kgs(total_b)}. Импортные позиции оплачиваются в USD "
              f"по курсу {_num(fx.usd) if fx else 0} сом/USD от {fx.date:%d.%m.%Y} "
              f"({fx.source if fx else '—'}); риск курса включён в реестр рисков."),
        *[("li", s) for s in rep["conclusions"]],
        ("h1", "11. Список источников"),
        *[("li", f"{i}. {s}") for i, s in enumerate(SOURCES, start=1)],
    ]
    return B


def _risk_matrix(risks: list[dict]) -> tuple:
    """Матрица 5×5: строки — влияние 5…1, столбцы — вероятность 1…5; в ячейках номера рисков."""
    cells = {(x["p"], x["i"]): [] for x in risks}
    for i, x in enumerate(risks, start=1):
        cells.setdefault((x["p"], x["i"]), []).append(i)
    head = ["Влияние \\ Вероятность"] + [str(p) for p in range(1, 6)]
    body = [[str(infl)] + [", ".join(map(str, cells.get((p, infl), []))) or "—"
                           for p in range(1, 6)] for infl in range(5, 0, -1)]
    return ("table", head, body)


def _deadline_note(project: Project) -> tuple:
    """Одна строка про резерв до крайних сроков вех (в рабочих днях календаря)."""
    from . import cpm
    s, cal = cpm.schedule(project)
    parts = []
    for t in project.leaf_tasks:
        if not t.deadline:
            continue
        fin = cal.finish_dt(s[t.key].ef).date()
        reserve = cal.day_of(t.deadline) - cal.day_of(fin)
        parts.append(f"{t.wbs} «{t.name}» — план {fin:%d.%m.%Y}, крайний срок "
                     f"{t.deadline:%d.%m.%Y}, запас {reserve} раб. дн")
    return ("p", "Крайние сроки вех: " + "; ".join(parts) + ".")


def _cost_section(project, data, phases, total, total_b, budget_kgs, fx, by_code) -> list[tuple]:
    """Подраздел 9.2: сводка по фазам, импортные позиции в USD, обоснование цен."""
    meta = project.meta
    base = meta.get("currency_code") or "RUB"
    out: list[tuple] = []
    if fx:
        rub_str = _rub(meta.get("budget_rub", 0))
        out += [("p",
                 f"Смета ведётся в базовой валюте — {meta.get('currency', base)}. "
                 f"Импортные позиции закупаются в USD и пересчитываются по формуле: "
                 f"сом = USD × {_num(fx.usd)}. Курс получен онлайн из XML НБКР "
                 f"(nbkr.kg/XML/daily.xml) на {fx.date:%d.%m.%Y} (источник: {fx.source}); "
                 f"фоллбэк — курсы ЦБ РФ. Бюджет методички: {rub_str} ₽ × {_num(fx.rub)} = "
                 f"{_kgs(budget_kgs)}.")]
    out += [
        ("table", ["Фаза", "Трудовые", "Материалы", "Затратные рес.", "Фикс. затраты", "Итого"],
         [[f"{w} {n}", _kgs(c["work"]), _kgs(c["material"]), _kgs(c["cost"]),
           _kgs(c["fixed"]), _kgs(c["total"])] for w, n, c in phases]
         + [["ИТОГО", "", "", "", "", _kgs(total)]]),
        ("p", f"Таблица норм затрат B (ставки подрядчика и внешних специалистов выше) — "
              f"{_kgs(total_b)}, разница {_kgs(total_b - total)}. Распределение по кодам "
              "работ: " + "; ".join(
             f"{k} ({project.work_codes[k]['name']}) — {_kgs(v)}, "
             f"{100 * v / total:.1f} %" for k, v in sorted(by_code.items(), key=lambda kv: -kv[1])) + "."),
    ]
    # Импортные позиции (валюта ресурса ≠ базовая валюта проекта)
    if fx:
        imp, kgs_total = [], 0.0
        for r in project.resources:
            if not r.currency or r.currency == base:
                continue
            kgs = qty = 0.0
            for t in project.leaf_tasks:
                u = t.res.get(r.key)
                if not u:
                    continue
                if r.type == "material":
                    qty += u
                    kgs += u * r.rate
                elif r.type == "cost":
                    kgs += u
            kgs_total += kgs
            f = fx.factor(r.currency, base)
            unit = (r.rate_src if r.rate_src else kgs / qty / f) if qty else kgs / f
            imp.append([r.name, r.currency, _usd(unit),
                        f"{qty:g} {r.label}" if qty else "—", _usd(kgs / f),
                        f"{_num(fx.usd)} сом/USD", _kgs(kgs)])
        if imp:
            out += [
                ("table", ["Позиция", "Валюта", "Цена за единицу", "Объём", "Сумма",
                           "Курс", "Сумма в сомах"], imp),
                ("p", f"Доля импортных позиций в смете — {_kgs(kgs_total)} "
                      f"({100 * kgs_total / total:.1f} % от плановой стоимости); оплата — "
                      f"в USD по курсу на дату заказа, отклонение курса > 5 % — пересчёт "
                      "сметы (см. риск в разделе 6)."),
            ]
    out += [("h3", "9.2.1. Обоснование цен (позиция → цена → источник → рынок)"),
            ("table", ["Позиция", "Цена", "Единица / объём", "Обоснование", "Диапазон рынка"],
             [[x["item"], x["price"], x["unit"], x["basis"], x["market"]]
              for x in data.get("cost_basis", [])]),
            ("p", "Валютный резерв (4 %) и порядок фиксации курса в договоре — в реестре "
                  "рисков (раздел 6) и в задаче «Обоснование сметы и валютная политика "
                  "проекта» (раздел 4).")]
    return out


# ---------- рендеры ----------

def markdown(B: list[tuple]) -> str:
    """Блоки → Markdown (для вычитки содержания без Word)."""
    out = []
    for b in B:
        kind = b[0]
        if kind in ("h1", "h2", "h3"):
            out.append("#" * int(kind[1]) + " " + b[1])
        elif kind == "p":
            out.append(b[1])
        elif kind == "li":
            out.append("- " + b[1])
        elif kind == "shot":
            out.append(f"> 📷 Скриншот `{b[2]}`: {b[1]}")
        elif kind == "table":
            head, rows = b[1], b[2]
            out.append("| " + " | ".join(head) + " |")
            out.append("|" + "---|" * len(head))
            out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |"
                    for r in rows]
        out.append("")
    return "\n".join(out)


def shot_ids(prefix: str) -> list[str]:
    """ID скриншотов ожидаемого формата: v12_01… (для автопроверок и automation)."""
    return [f"{prefix}_{i:02d}" for i in range(1, 6)]


def docx(project: Project, data: dict, path: Path, prefix: str) -> Path:
    """Собрать .docx практической работы: титул, содержание (поле TOC), разделы.

    A4, поля 2 см, Times New Roman 12 (таблицы 9); каждый раздел с новой
    страницы; скриншоты — метки SHOT_MARK + подпись «Рисунок».
    """
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    meta = project.meta
    B = blocks(project, data, prefix)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2)

    def _font(style, size, bold=False):
        style.font.name, style.font.size = "Times New Roman", Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor(0, 0, 0)
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        for slot in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(slot), "Times New Roman")

    _font(doc.styles["Normal"], 12)
    for lvl, size in ((1, 14), (2, 13), (3, 12)):
        _font(doc.styles[f"Heading {lvl}"], size, bold=True)

    # Титул
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run("ДОПОЛНИТЕЛЬНОЕ ЗАДАНИЕ\nпо дисциплине «Управление проектами "
              "в информационной безопасности»\n\n").bold = True
    t.add_run(f"на тему «Планирование проекта внедрения СЗИ: "
              f"{meta['system']}»\nВариант {meta['variant']} — {meta.get('variant_note', '')}\n\n")
    t.add_run(f"Выполнил(а): {meta.get('author', '________')} ____________________\n"
              "Проверил(а): ____________________\n\n")
    t.add_run("— 2026 —")
    doc.add_page_break()

    # Содержание (поле TOC: обновляется в Word — ПКМ «Обновить поле»)
    h = doc.add_paragraph()
    h.add_run("Содержание").bold = True
    p = doc.add_paragraph()
    run = p.add_run()
    for tag, attrs, text in (("w:fldChar", {"w:fldCharType": "begin"}, None),
                             ("w:instrText", {"xml:space": "preserve"},
                              'TOC \\o "1-2" \\h \\z \\u'),
                             ("w:fldChar", {"w:fldCharType": "separate"}, None),
                             ("w:t", {}, "[ Обновите поле: ПКМ по содержанию → Обновить поле ]"),
                             ("w:fldChar", {"w:fldCharType": "end"}, None)):
        el = OxmlElement(tag)
        for k, v in attrs.items():
            el.set(qn(k), v)
        if text:
            el.text = text
        run._r.append(el)
    doc.add_page_break()

    first = True
    for b in B:
        kind = b[0]
        if kind == "h1":
            if not first:
                doc.add_page_break()
            first = False
            doc.add_heading(b[1], level=1)
        elif kind in ("h2", "h3"):
            doc.add_heading(b[1], level=int(kind[1]))
        elif kind == "p":
            doc.add_paragraph(b[1])
        elif kind == "li":
            doc.add_paragraph(b[1], style="List Bullet")
        elif kind == "shot":
            par = doc.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = par.add_run(SHOT_MARK.format(id=b[2], caption=b[1]))
            r.italic = True
            r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
            cap = doc.add_paragraph(f"Рисунок — {b[1]}")
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "table":
            head, rows = b[1], b[2]
            tbl = doc.add_table(rows=1, cols=len(head))
            tbl.style = "Table Grid"
            for i, htxt in enumerate(head):
                cell = tbl.rows[0].cells[i]
                cell.text = ""
                cell.paragraphs[0].add_run(str(htxt)).bold = True
            for row in rows:
                cells = tbl.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = str(v)
            for row in tbl.rows:
                for cell in row.cells:
                    for par in cell.paragraphs:
                        for run in par.runs:
                            run.font.size = Pt(9)
            doc.add_paragraph()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path
