"""Независимый расчёт расписания (метод критического пути), стоимости и загрузки.

Время считается в рабочих часах от начала проекта (индекс часа), календарь —
пятидневка по 8 ч с исключениями из project.yaml. Правила повторяют MS Project
для проекта, планируемого от даты начала:
  ОН: начало ≥ окончание предш. + лаг;  НН: начало ≥ начало предш. + лаг;
  ОО: окончание ≥ окончание предш. + лаг;  НО: окончание ≥ начало предш. + лаг;
  «Начало не ранее» — нижняя граница раннего начала; крайний срок ограничивает
  позднее окончание (как в MS Project, влияет на резерв).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from .model import HOURS_PER_DAY, Project, Task

H = HOURS_PER_DAY


class Calendar:
    """Рабочий календарь: сплошной список рабочих дней и перевод «индекс часа → дата/время».

    Часовой индекс — позиция часа от начала проекта, только по рабочим дням:
    `days[i] * 8 + слот в дне`. Таблица `days` конечна (`horizon_days`), дальше
    индексов просто нет.
    """

    def __init__(self, project: Project, horizon_days: int = 800):
        # 800 раб. дней (~3 года) — предел таблицы дней, а не «настройка плана»:
        # текущий план занимает ~5 месяцев, и запас нужен, чтобы правки
        # project.yaml, погрешности и отрицательный резерв не упирались в границу.
        # За пределом day_of()/индексация возвращают IndexError, а не мягкий отказ.
        off: set[dt.date] = set()
        for a, b, _ in project.exceptions():
            d = a
            while d <= b:
                off.add(d)
                d += dt.timedelta(days=1)
        self.days: list[dt.date] = []
        d = project.start
        while len(self.days) < horizon_days:
            if d.weekday() < 5 and d not in off:
                self.days.append(d)
            d += dt.timedelta(days=1)
        self.index = {d: i for i, d in enumerate(self.days)}
        # Два блока дня из calendar.work_hours (08–12 и 13–17): обед 12–13 не
        # входит в 8 рабочих часа и вычитается при переводе слота в настенное время.
        (s1, e1), (s2, e2) = project.calendar["work_hours"]
        self.morning = int(s1[:2])
        self.lunch = int(e1[:2]), int(s2[:2])

    def day_of(self, date: dt.date) -> int:
        """Индекс первого рабочего дня не раньше date."""
        while date not in self.index:
            date += dt.timedelta(days=1)
        return self.index[date]

    def _clock(self, off: int, finish: bool) -> dt.time:
        # Слот внутри дня идёт сплошным 0..7, а настенные часы пропускают обед:
        # 0–3 → 08–11, 4–7 → 13–16. Для окончания слот 4 закрывает утренний
        # блок в 12:00, слот 7 — послеобеденный в 17:00.
        before_lunch = self.lunch[0] - self.morning
        if off < before_lunch or (finish and off == before_lunch):
            return dt.time(self.morning + off)
        return dt.time(self.lunch[1] + off - before_lunch)

    def start_dt(self, h: float) -> dt.datetime:
        """Часовой индекс → дата/время начала: слот показывается от его начала (08:00, 13:00, ...)."""
        d, off = divmod(int(round(h)), H)
        return dt.datetime.combine(self.days[d], self._clock(off, False))

    def finish_dt(self, h: float) -> dt.datetime:
        """Часовой индекс → дата/время окончания: конец слота, как его показывает MS Project."""
        # MS Project показывает окончание в конце слота, а не в его начале:
        # h, приходящийся на границу дня (08:00 следующего), откатывается на
        # конец предыдущего рабочего дня (17:00). Так же ведёт себя
        # MicrosoftScheduler — тест сверяет с ним начало и окончание каждой задачи.
        d, off = divmod(int(round(h)), H)
        if off == 0 and d > 0:
            d, off = d - 1, H
        return dt.datetime.combine(self.days[d], self._clock(off, True))


@dataclass
class Sched:
    """Ранние и поздние даты задачи в часовых индексах; резерв = ls − es.

    Отрицательный резерв возможен у задач с крайним сроком: позднее окончание
    зажато дедлайном раньше раннего (MS Project показывает это как перегрузку
    крайнего срока).
    """

    es: float
    ef: float
    ls: float = 0.0
    lf: float = 0.0

    @property
    def slack(self) -> float:
        return self.ls - self.es


def topo_order(project: Project) -> list[Task]:
    """Листовые задачи так, что предшественник всегда идёт раньше своего преемника.

    Raises:
        ValueError: в связях цикл или указан неизвестный ключ предшественника —
            ошибка данных project.yaml, дальше считать расписание нельзя.
    """
    leaves = {t.key: t for t in project.leaf_tasks}
    # Нет ключа — не начат, 1 — в обходе (встретили повторно → цикл), 2 — завершён.
    state: dict[str, int] = {}
    out: list[Task] = []

    def visit(k: str, stack: tuple = ()):
        if state.get(k) == 2:
            return
        if state.get(k) == 1:
            raise ValueError("Цикл в связях: " + " → ".join(stack + (k,)))
        state[k] = 1
        for ln in leaves[k].links:
            if ln.pred not in leaves:
                raise ValueError(f"{k}: неизвестный предшественник {ln.pred}")
            visit(ln.pred, stack + (k,))
        state[k] = 2
        out.append(leaves[k])

    for k in leaves:
        visit(k)
    return out


def schedule(project: Project) -> tuple[dict[str, Sched], Calendar]:
    """Ранние и поздние даты всех задач плюс использованный календарь.

    Два прохода по топологическому порядку: вперёд (ранние) и назад (поздние).
    Крайний срок влияет только на позднее окончание, поэтому даты начала и
    окончания в отчёте от него не меняются — меняется лишь резерв. Фазы получают
    агрегаты детей (min/max), собственных связей у них нет.

    Returns:
        ({ключ задачи: Sched}, Calendar); времена — в часовых индексах.
    """
    cal = Calendar(project)
    order = topo_order(project)
    s: dict[str, Sched] = {}
    for t in order:
        d = t.dur_days * H
        es = 0.0
        for ln in t.links:
            p, lag = s[ln.pred], ln.lag_days * H
            es = max(es, {"FS": p.ef + lag, "SS": p.es + lag,
                          "FF": p.ef + lag - d, "SF": p.es + lag - d}[ln.type])
        if t.constraint and t.constraint["type"] == "SNET":
            es = max(es, cal.day_of(t.constraint["date"]) * H)
        s[t.key] = Sched(es, es + d)
    finish = max(x.ef for x in s.values())
    succ = defaultdict(list)
    for t in order:
        for ln in t.links:
            succ[ln.pred].append((t, ln))
    for t in reversed(order):
        d = t.dur_days * H
        lf = finish
        for st, ln in succ[t.key]:
            x, lag = s[st.key], ln.lag_days * H
            lf = min(lf, {"FS": x.ls - lag, "SS": x.ls - lag + d,
                          "FF": x.lf - lag, "SF": x.lf - lag + d}[ln.type])
        if t.deadline:
            # Крайний срок — конец своего дня, а не его начало: (+1) переводит
            # индекс дня в часовой индекс конца суток, чтобы завершение в 17:00
            # в день дедлайна нарушением ещё не считалось (как в MS Project).
            lf = min(lf, (cal.day_of(t.deadline) + 1) * H)
        s[t.key].lf, s[t.key].ls = lf, lf - d
    for t in project.tasks:
        if t.summary:
            kids = [s[k] for k in t.children]
            s[t.key] = Sched(min(k.es for k in kids), max(k.ef for k in kids),
                             min(k.ls for k in kids), max(k.lf for k in kids))
    return s, cal


def critical_keys(project: Project, s: dict[str, Sched]) -> list[str]:
    """Ключи листовых задач с нулевым резервом — критический путь проекта."""
    # 1e-9 — допуск сравнения с нулём, а не «почти ноль по вкусу»: резерв
    # считается вычитанием часовых индексов, и нулевой на деле приходит как
    # 1e-13. Жёсткое slack == 0 пометило бы часть некритических задач.
    # Тот же допуск применён во всех проверках «резерв равен нулю» по коду.
    return [t.key for t in project.leaf_tasks if s[t.key].slack <= 1e-9]


# ---------- стоимость ----------

def rate_on(r, date: dt.date, table: str = "A") -> float:
    """Ставка ресурса на дату для таблицы норм затрат A или B.

    Таблица B — одна ставка на весь период: дата действия из таблицы A к ней
    не применяется (так же считает MS Project: таблица выбрана целиком).
    """
    if table == "B" and r.rate_b is not None:
        return r.rate_b
    if r.rate_change and date >= r.rate_change["from"]:
        return r.rate_change["rate"]
    return r.rate


def hours_by_day(start_h: float, end_h: float) -> dict[int, float]:
    """Часы интервала [start_h, end_h), разложенные по индексам рабочих дней.

    Нужно и для стоимости (ставка своя на каждый день — смена даты действия
    применяется к конкретному дню), и для перегрузок (лимит проверяется на
    каждый день отдельно).
    """
    out: dict[int, float] = defaultdict(float)
    h = start_h
    # −1e-9 — допуск на float-погрешность конца интервала: без него хвост ~1e-13 ч
    # давал бы в словаре отдельный день с практически нулевыми часами — мусор в
    # стоимости и ложная «ненулевая» нагрузка там, где день проверяется
    # truthiness-ом (выбор задач-конфликтов в analysis.overalloc_summary).
    while h < end_h - 1e-9:
        d = int(h // H)
        nxt = min(end_h, (d + 1) * H)
        out[d] += nxt - h
        h = nxt
    return out


def costs(project: Project, s, cal, table: str = "A") -> dict[str, dict]:
    """Стоимость по задачам: трудовые, материальные, затратные ресурсы и фиксированные затраты.

    Returns:
        {ключ задачи: {"work", "material", "cost", "fixed", "hours", "total"}}
        в рублях (часы — для сводок); для фаз — сумма по детям.
    """
    res = {r.key: r for r in project.resources}
    out: dict[str, dict] = {}
    for t in project.leaf_tasks:
        c = {"work": 0.0, "material": 0.0, "cost": 0.0, "fixed": t.fixed_cost, "hours": 0.0}
        for rk, u in t.res.items():
            r = res[rk]
            if r.type == "work":
                for d, hrs in hours_by_day(s[t.key].es, s[t.key].ef).items():
                    c["work"] += hrs * u * rate_on(r, cal.days[d], table)
                    c["hours"] += hrs * u
                # Per Use начисляется на каждую единицу назначения: "It is added each time
                # a work resource unit is assigned to a task" (Microsoft, Cost Per Use field)
                c["work"] += r.per_use * u
            elif r.type == "material":
                # Материал не зависит от времени: списывается количество × цена
                # (u — уже штуки/листы, а не проценты загрузки).
                c["material"] += u * r.rate
            else:
                # Затратный ресурс: единица назначения — это сама сумма в рублях
                # (например, аренда на задачу целиком).
                c["cost"] += u
        c["total"] = c["work"] + c["material"] + c["cost"] + c["fixed"]
        out[t.key] = c
    for t in project.tasks:
        if t.summary:
            # Стоимость фазы — сумма деталей, как в MS Project: у суммарной
            # задачи нет собственных назначений.
            out[t.key] = {k: sum(out[ch][k] for ch in t.children) for k in out[t.children[0]]}
    return out


# ---------- загрузка ресурсов ----------

def capacity(r, date: dt.date) -> float:
    """Доступность ресурса на дату в долях (1.0 = 100 %).

    Берётся первая подошедшая запись таблицы доступности; периоды в
    project.yaml задаются непересекающимися, поэтому порядок записей на
    результат не влияет. Записей нет — ресурс доступен всегда.
    """
    for a in r.availability:
        if a["from"] <= date and (a["to"] is None or date <= a["to"]):
            return a["units"]
    return 1.0


def overallocations(project: Project, s, cal) -> dict[str, list[tuple[dt.date, float, float]]]:
    """{ресурс: [(дата, назначено ч, доступно ч)]} для дней с превышением доступности.

    Учитываются только трудовые ресурсы: у материальных и затратных «лимита на
    день» нет, перегрузка для них не определена.
    """
    load: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for t in project.leaf_tasks:
        for rk, u in t.res.items():
            if project.resource(rk).type != "work":
                continue
            for d, hrs in hours_by_day(s[t.key].es, s[t.key].ef).items():
                load[rk][d] += hrs * u
    out: dict[str, list] = {}
    for rk, days in load.items():
        r = project.resource(rk)
        # +1e-9 — тот же допуск сравнения, что в critical_keys: назначение
        # ровно в лимит не является превышением.
        bad = [(cal.days[d], h, capacity(r, cal.days[d]) * H) for d, h in sorted(days.items())
               if h > capacity(r, cal.days[d]) * H + 1e-9]
        if bad:
            out[rk] = bad
    return out
