"""Расчётная часть для отчёта: расписание, PERT, критический путь, стоимость, перегрузки.

Всё считается из модели через cpm — отдельных чисел в коде нет. Возвращаемые
структуры кормят report (Markdown и .docx) и expected.json для сверки с MS
Project на ВМ.
"""
from __future__ import annotations

import copy
import datetime as dt
from collections import defaultdict

from . import cpm
from .model import HOURS_PER_DAY as H, Project, pert_days, with_pert_durations


def fmt_d(x: dt.datetime) -> str:
    """Дата в формате отчёта: дд.мм.гггг чч:мм — как её показывает MS Project."""
    return x.strftime("%d.%m.%Y %H:%M")


def fmt_days(hours: float) -> str:
    """Часы → длительность в днях: целые дни печатаются без дробной части, остальные — с двумя знаками."""
    # Часы → дни; 1e-9 — допуск float: 4.0000000000001 должен печататься как
    # «4 дн.», а не как «4,00 дн.» (целые дни в таблицах без дробной части).
    d = hours / H
    return f"{d:g} дн." if abs(d - round(d)) < 1e-9 else f"{d:.2f} дн."


def money(x: float) -> str:
    """Сумма в рублях для отчёта: «12 345,67 ₽» — разряды пробелом, дробная часть через запятую."""
    # Русская запись суммы вручную: разряды пробелом, дробная часть через запятую —
    # locale в скрипте не выставляется, format переворачивал бы разделители.
    return f"{x:,.2f} ₽".replace(",", " ").replace(".", ",")


def finish_of(project: Project) -> dt.datetime:
    """Дата и время окончания проекта: самое позднее окончание среди задач."""
    s, cal = cpm.schedule(project)
    return cal.finish_dt(max(v.ef for v in s.values()))


def schedule_rows(project: Project):
    """Строки таблицы расписания для отчёта — по одной на задачу или фазу, в порядке WBS.

    У вехи начало берётся как время окончания (в MS нулевая задача показывается
    на границе слота), у фаз резерв пуст: резерв считается только по листовым
    задачам.
    """
    s, cal = cpm.schedule(project)
    rows = []
    for t in project.tasks:
        x = s[t.key]
        start = cal.finish_dt(x.es) if t.milestone else cal.start_dt(x.es)
        rows.append({
            "wbs": t.wbs, "name": t.name, "summary": t.summary, "milestone": t.milestone,
            "dur": fmt_days(x.ef - x.es), "start": fmt_d(start), "finish": fmt_d(cal.finish_dt(x.ef)),
            "slack": fmt_days(x.slack) if not t.summary else "",
            "critical": (not t.summary and x.slack <= 1e-9),
            "preds": ", ".join(_pred_text(project, ln) for ln in t.links),
            "res": ", ".join(_res_text(project, k, u) for k, u in t.res.items()),
        })
    return rows


def _pred_text(project: Project, ln) -> str:
    """Предшественник для таблицы: «5.8» либо «5.8ОН+2 дн.» — код скрыт, если связь обычная ОН без лага."""
    ru = {"FS": "ОН", "SS": "НН", "FF": "ОО", "SF": "НО"}[ln.type]
    wbs = project.task(ln.pred).wbs
    if ln.type == "FS" and not ln.lag_days:
        return wbs
    lag = f"{ln.lag_days:+g} дн." if ln.lag_days else ""
    return f"{wbs}{ru}{lag}"


def _res_text(project: Project, key: str, u: float) -> str:
    """Назначение ресурса для таблицы отчёта: имя плюс единицы в скобках.

    Например «Смирнова А.В.» (ровно 100 %), «Орлова Е.Н.[50 %]»,
    «Печать анкет[200 лист]», «Аренда сервера и домена[18 000 ₽]».
    """
    r = project.resource(key)
    if r.type == "work":
        return r.name if u == 1 else f"{r.name}[{u * 100:g}%]"
    if r.type == "material":
        return f"{r.name}[{u:g} {r.label}]"
    return f"{r.name}[{money(u)}]"


def pert_table(project: Project, weights_list=((1, 4, 1), (1, 3, 2), (1, 2, 3))):
    """Таблица PERT-оценок и окончания проекта для каждого набора весов.

    Returns:
        (строки таблицы, {набор весов или "p=m": окончание проекта}). Строки
        строятся только по невеховым задачам с оценками; «p = m» — отдельный
        сюжет задания 9 ЛР8 (пессимистическая оценка равна наиболее вероятной).
    """
    rows = []
    for t in project.leaf_tasks:
        if t.milestone or not t.pert:
            continue
        o, m, p = t.pert
        # σ = (П − О)/6: в PERT весь диапазон между оптимистичной и пессимистичной
        # оценкой принимается равным шести стандартным отклонениям.
        rows.append({"wbs": t.wbs, "name": t.name, "o": o, "m": m, "p": p,
                     **{f"e{w}": round(pert_days(o, m, p, w), 2) for w in weights_list},
                     "sigma": round((p - o) / 6, 2)})
    # Окончание зависит от подменённых длительностей — для каждого набора весов
    # расписание считается заново на своей копии.
    finishes = {w: finish_of(with_pert_durations(project, w)) for w in weights_list}
    # задание 9 ЛР8: пессимистические сроки совпадают с ожидаемыми
    same = copy.deepcopy(project)
    for t in same.leaf_tasks:
        if t.pert and not t.milestone:
            t.pert = (t.pert[0], t.pert[1], t.pert[1])
    # Пересборка индексов: копия мутировала (PERT перезаписан), task() должен
    # видеть новые объекты.
    same.__post_init__()
    finishes["p=m"] = finish_of(with_pert_durations(same, (1, 4, 1)))
    return rows, finishes


def critical_path_variance(project: Project):
    """Сумма дисперсий PERT по критическому пути (для оценки вероятности срока).

    Returns:
        (список критических ключей, σ = √суммы дисперсий) в днях. Считается на
        копии без крайних сроков: резерв с дедлайном зажат, а «настоящий»
        критический путь определяется без него.
    """
    p = with_pert_durations(project)
    for t in p.tasks:
        t.deadline = None          # путь без учёта крайнего срока
    s, _ = cpm.schedule(p)
    crit = cpm.critical_keys(p, s)
    # (П − О)/6 — то же σ PERT, что в pert_table; на критическом пути
    # дисперсии независимых задач складываются (σ² суммы = сумма σ²).
    var = sum(((project.task(k).pert[2] - project.task(k).pert[0]) / 6) ** 2
              for k in crit if project.task(k).pert)
    return crit, var ** 0.5


def cost_summary(project: Project, table: str = "A"):
    """Сводка затрат для отчёта ЛР5/ЛР9.

    Args:
        table: таблица норм затрат A или B; B перекрывает дату действия из A.

    Returns:
        (строки по фазам, итог, по верхнему коду работ, по ресурсам, пом задачам).
    """
    s, cal = cpm.schedule(project)
    c = cpm.costs(project, s, cal, table)
    phases = [(t.wbs, t.name, c[t.key]) for t in project.tasks if t.summary]
    total = sum(x[2]["total"] for x in phases)
    by_code = defaultdict(float)
    for t in project.leaf_tasks:
        if t.code:
            by_code[t.code.split(".")[0]] += c[t.key]["total"]
    by_res = defaultdict(float)
    for t in project.leaf_tasks:
        for rk, u in t.res.items():
            r = project.resource(rk)
            if r.type == "work":
                for d, hrs in cpm.hours_by_day(s[t.key].es, s[t.key].ef).items():
                    by_res[r.name] += hrs * u * cpm.rate_on(r, cal.days[d], table)
                # Формула повторяет cpm.costs намеренно: сводка по ресурсам
                # собирается своим проходом (там сводка по задачам), вычитать
                # из неё нельзя — обе должны давать один итог.
                by_res[r.name] += r.per_use * u  # как в cpm.costs: за каждую единицу назначения
            elif r.type == "material":
                by_res[r.name] += u * r.rate
            else:
                by_res[r.name] += u
    return phases, total, dict(by_code), dict(by_res), c


def overalloc_summary(project: Project):
    """Сводка перегрузок для ЛР6: ресурс, число дней, пик, периоды и задачи-конфликты.

    Пик — отношение назначено/доступно (может быть ∞ при доступности 0 %).
    """
    s, cal = cpm.schedule(project)
    out = []
    for rk, days in cpm.overallocations(project, s, cal).items():
        r = project.resource(rk)
        periods = []
        for d, h, capa in days:
            # Склейка одинаковых пиков через короткий разрыв: 3 календарных дня —
            # это как раз выходные между пятницей и понедельником, а перерыв
            # длиннее (или другой профиль нагрузки) уже новая строка в отчёте.
            if periods and (d - periods[-1][1]).days <= 3 and periods[-1][2] == (h, capa):
                periods[-1][1] = d
            else:
                periods.append([d, d, (h, capa)])
        tasks = sorted({t.wbs for t in project.leaf_tasks if rk in t.res
                        and any(cpm.hours_by_day(s[t.key].es, s[t.key].ef).get(cal.index[d])
                                for d, _, _ in days)})
        out.append({"res": r.name, "days": len(days), "peak": max(h / capa if capa else float("inf")
                                                                   for _, h, capa in days),
                    "periods": [(a, b, h, capa) for a, b, (h, capa) in periods], "tasks": tasks})
    return out


def crash_scenarios(project: Project):
    """ЛР9, задания 2–5: способы сокращения критического пути и их эффект на срок.

    Returns:
        [(метка, окончание проекта, что изменено)] — исходный план плюс пять
        вариантов. Метки и порядок стабильны: их же сверяет скрипт с
        out/expected.json, поэтому подписи не редактируются «для красоты».

    Ключи задач ("website" — 4.1 «Создание сайта конференции», "mailout" —
    веха «Материалы готовы») взяты из project.yaml: условие ЛР9 привязывает все
    способы именно к этой критической задаче, поэтому ключи — не параметры
    функции. Переименование их в YAML сломает только эти сценарии — тесты об
    этом напомнят.
    """
    base = finish_of(project)
    res = [("Исходный план", base, "—")]

    def variant(label, fn, how):
        p = copy.deepcopy(project)
        fn(p)
        # Индексы task() пересобираются: вариант мог вставить новые задачи или
        # переименовать — без этого lookup отдал бы объекты старой копии.
        p.__post_init__()
        res.append((label, finish_of(p), how))

    # Цель — 4.1 «Создание сайта конференции»: критическая задача, связь ОН с «Рассылка первого сообщения».
    def less_work(p):
        # 6 → 4 дн.: сокращение ровно на 2 дня, чтобы эффект читался в отчёте
        # (объём работ уменьшаем, а не «пришпориваем» ресурсами).
        p.task("website").dur_days = 4
    variant("1) Сократить объём работ критической задачи", less_work,
            "4.1 «Создание сайта конференции»: 6 → 4 дн. (контент перенесён в отдельную задачу)")

    def more_res(p):
        # Фиксированный объём работ: 48 ч (6 дн. × 8 ч) делятся на две единицы,
        # поэтому длительность падает вдвое — ровно так же MS пересчитает её,
        # когда студент поставит тип «Фиксированный объём работ».
        t = p.task("website")
        t.res = {"UX": 1.0, "FE": 1.0}
        t.dur_days = 6 / 2
    variant("2) Добавить ресурс без изменения объёма", more_res,
            "4.1: тип «Фиксированный объём работ» + Смирнова А.В. 100 %: 48 ч / 2 ед. = 3 дн.")

    def split(p):
        from .model import Link, Task
        t = p.task("website")
        t.name, t.dur_days = "Сайт: дизайн и вёрстка", 3
        # Новая задача наследует связи исходной и уходит тем же кодом работ:
        # обе половины — та же ПР.САЙТ, что и у 4.1.
        new = Task(key="website2", name="Сайт: наполнение и тексты", wbs="4.1.2", level=2,
                   dur_days=3, pert=(2, 3, 5), links=list(t.links), res={"FE": 1.0}, code="ПР.САЙТ")
        p.tasks.insert(p.tasks.index(t) + 1, new)
        next(ph for ph in p.tasks if "website" in ph.children).children.append("website2")
        # Вторая половина должна тоже заканчиваться у задачи «Рассылка первого сообщения»:
        # связь переносится вручную, иначе задача выпадет из критического пути
        # и эффект сценария исказится.
        p.task("mailout").links.append(Link("website2"))
    variant("3) Разбить задачу на две параллельные", split,
            "4.1 → «дизайн и вёрстка» (Петров, 3 дн.) ‖ «наполнение и тексты» (Смирнова, 3 дн.)")

    shifted = copy.deepcopy(project)
    shifted.meta["start"] = project.start + dt.timedelta(days=7)
    shifted.__post_init__()
    res.append(("4) Начало проекта сдвинуто на неделю", finish_of(shifted),
                "срок позже крайнего срока вехи 5.5 — появляется отрицательный резерв"))
    # Комбинация «сдвиг + ресурс»: показывает, что способ 2 возвращает проект
    # в крайний срок даже после недельного опоздания старта.
    fixed = copy.deepcopy(shifted)
    more_res(fixed)
    fixed.__post_init__()
    res.append(("5) Сдвиг на неделю + ресурс на 4.1", finish_of(fixed),
                "как в способе 2: + Смирнова А.В. 100 % на 4.1 → 3 дн., проект снова укладывается в крайний срок"))
    return res
