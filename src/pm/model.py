"""Загрузка project.yaml в плоскую модель: задачи с WBS, связями и назначениями.

`project.yaml` — единственный источник данных, модель — единственный вход для
расчёта (cpm), выгрузки (msproject), анализа и отчёта. Инварианты: ключи задач
уникальны, а имена уникальны среди задач — имена нужны для сопоставления задач при
обратном чтении выгруженного XML.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Календарное допущение всего тулкита: 8-часовой рабочий день (пн–пт, 08–12 и
# 13–17, см. calendar.work_hours). Длительности в модели хранятся в днях, а время
# расписания в cpm считается в часах — «день» там равен 8 часовым слотам.
# Менять только синхронно с календарём в project.yaml.
HOURS_PER_DAY = 8
# Русские сокращения типов связей из методички → коды MS Project/MPXJ. Читаются
# по-русски («окончание–начало»), поэтому ОН — это FS, а не SS; по этому же
# принципу ОО = FF, НН = SS, НО = SF.
LINK_TYPES = {"ОН": "FS", "НН": "SS", "ОО": "FF", "НО": "SF"}
# Грамматика строки связи в project.yaml: ключ | ключ:ТИП | ключ:ТИП±лаг (лаг в
# днях, дробный допустим), например "design:НН+3". Без типа и лага — связь ОН,
# это тип связи MS Project по умолчанию.
LINK_RE = re.compile(r"^(?P<key>[\w]+)(?::(?P<type>ОН|НН|ОО|НО)(?P<lag>[+-]\d+(?:\.\d+)?)?)?$")


@dataclass
class Link:
    """Связь задачи с предшественником; `lag_days` — запаздывание в рабочих днях (может быть отрицательным)."""

    pred: str
    type: str = "FS"     # FS | SS | FF | SF
    lag_days: float = 0.0


@dataclass
class Task:
    """Задача проекта: фаза (summary) или листовая задача с ресурсами и связями.

    Единицы и форматы: `dur_days` — рабочие дни (8 ч); `pert` — тройка
    (оптимистичная, наиболее вероятная, пессимистическая) в днях; `res` —
    {ключ ресурса: единицы}, где трудовой ресурс — доли (1.0 = 100 %),
    материальный — количество (шт.), затратный — сумма в рублях; `code` — «Код
    работ» вида «РАЗ.FE» (два уровня через точку, как и коды отделов).
    """

    key: str
    name: str
    wbs: str
    level: int                      # 1 — фаза, 2 — задача
    summary: bool = False
    dur_days: float = 0.0
    pert: tuple[float, float, float] | None = None
    links: list[Link] = field(default_factory=list)
    res: dict[str, float] = field(default_factory=dict)
    code: str | None = None
    note: str | None = None
    link_url: str | None = None
    constraint: dict | None = None      # {"type": "SNET", "date": date} — см. словарь CONSTRAINT в msproject
    deadline: dt.date | None = None     # крайний срок: режет позднее окончание (резерв), не ранние даты
    fixed_cost: float = 0.0
    accrual: str = "prorated"           # start | end | prorated — когда MS начисляет фиксированные затраты
    children: list[str] = field(default_factory=list)   # ключи подзадач; заполняется только у фаз

    @property
    def milestone(self) -> bool:
        """Веха — листовая задача с нулевой длительностью; суммарные фазы вехами не бывают."""
        return not self.summary and self.dur_days == 0


@dataclass
class Resource:
    """Ресурс проекта; `type` задаёт и единицы, и набор применяемых полей.

    work: `rate`/`ot`/`rate_b` — ₽/ч (таблицы норм затрат A и B), `rate_change` —
    вторая ставка таблицы A с даты действия, `per_use` — «Затраты за
    использование» (начисляются на каждую единицу назначения, см. cpm.costs).
    material: `rate` — ₽ за единицу, `label` — единица измерения («шт.»).
    cost: сумма задаётся в назначении задачи, ставки не нужны.
    `availability` — периоды доступности в долях (0.5 = 50 %), `to: null` —
    бессрочно.
    """

    key: str
    name: str
    type: str = "work"              # work | material | cost
    role: str | None = None
    initials: str | None = None
    group: str | None = None
    dept: str | None = None
    label: str | None = None
    rate: float = 0.0
    ot: float = 0.0
    rate_b: float | None = None
    per_use: float = 0.0
    rate_change: dict | None = None
    availability: list[dict] = field(default_factory=list)
    currency: str | None = None       # валюта цены (USD для импорта); None — базовая проекта
    rate_src: float | None = None     # цена до конвертации (заполняет currency.apply_fx)


@dataclass
class Project:
    """Метаданные, календарь, ресурсы и задачи в порядке структуры WBS.

    Доступ по ключу (`task()`, `resource()`) идёт через индексы из
    `__post_init__`: после вставки/удаления элементов в `tasks` индекс нужно
    перестроить ещё раз, иначе lookup не увидит новые задачи (так делают
    сценарии сокращения критического пути в analysis).
    """

    meta: dict
    calendar: dict
    resources: list[Resource]
    tasks: list[Task]                # в порядке структуры (фаза, её задачи, ...)
    work_codes: dict
    dept_codes: dict

    @property
    def start(self) -> dt.date:
        return self.meta["start"]

    def task(self, key: str) -> Task:
        """Задача по ключу из project.yaml; неизвестный ключ — KeyError, а не None."""
        return self._by_key[key]

    def resource(self, key: str) -> Resource:
        """Ресурс по ключу из project.yaml; неизвестный ключ — KeyError, а не None."""
        return self._res_by_key[key]

    def __post_init__(self):
        self._by_key = {t.key: t for t in self.tasks}
        self._res_by_key = {r.key: r for r in self.resources}

    @property
    def leaf_tasks(self) -> list[Task]:
        """Всё, кроме фаз: рабочие задачи и вехи (именно они участвуют в расчёте CPM)."""
        return [t for t in self.tasks if not t.summary]

    def exceptions(self) -> list[tuple[dt.date, dt.date, str]]:
        """Нерабочие периоды календаря как (с, по, название) — в этом виде их ждёт MS Project."""
        return [(e["from"], e["to"], e["name"]) for e in self.calendar.get("exceptions", [])]


def parse_link(spec: str) -> Link:
    """Разобрать строку связи вида «ключ[:ТИП[±лаг]]» из project.yaml.

    Raises:
        ValueError: строка не соответствует грамматике связей (см. LINK_RE).
    """
    m = LINK_RE.match(spec.strip())
    if not m:
        raise ValueError(f"Неверная связь: {spec!r}")
    return Link(m["key"], LINK_TYPES[m["type"] or "ОН"], float(m["lag"] or 0))


def load(path: str | Path) -> Project:
    """Прочитать project.yaml и построить модель.

    Фазы и WBS создаются автоматически по порядку следования: каждая фаза
    попадает в список задач первой, за ней — её задачи. Вехи получают PERT
    (0, 0, 0), чтобы PERT-поля и таблицы отчёта были заполнены и для них.

    Args:
        path: путь к project.yaml.

    Returns:
        Модель с задачами в порядке структуры (фаза, затем её задачи).
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    tasks: list[Task] = []
    for pi, ph in enumerate(data["phases"], start=1):
        phase = Task(key=f"phase{pi}", name=ph["name"], wbs=str(pi), level=1, summary=True)
        tasks.append(phase)
        for ti, t in enumerate(ph["tasks"], start=1):
            task = Task(
                key=t["key"], name=t["name"], wbs=f"{pi}.{ti}", level=2,
                dur_days=float(t.get("dur", 0)),
                pert=tuple(t["pert"]) if "pert" in t else None,
                links=[parse_link(s) for s in t.get("after", [])],
                res={k: float(v) for k, v in (t.get("res") or {}).items()},
                code=t.get("code"), note=t.get("note"), link_url=t.get("link"),
                constraint=t.get("constraint"), deadline=t.get("deadline"),
                fixed_cost=float(t.get("fixed_cost", 0)), accrual=t.get("accrual", "prorated"),
            )
            if task.milestone and task.pert is None:
                task.pert = (0, 0, 0)
            tasks.append(task)
            phase.children.append(task.key)
    resources = [Resource(**r) for r in data["resources"]]
    project = Project(data["project"], data["calendar"], resources, tasks,
                      data.get("work_codes", {}), data.get("dept_codes", {}))
    # Блок fx — курсы онлайн-замера; с ним цены валютных ресурсов переводятся
    # в базовую валюту, чтобы расписание, смета и XML MS Project считали одно.
    from . import currency               # локально: currency импортирует model
    fx = currency.from_yaml(data)
    if fx:
        currency.apply_fx(project, fx)
    return project


def pert_days(o: float, m: float, p: float, weights=(1, 4, 1)) -> float:
    """Ожидаемая длительность по PERT: взвешенное среднее трёх оценок.

    Args:
        o: оптимистичная оценка, дня.
        m: наиболее вероятная оценка, дня.
        p: пессимистичная оценка, дня.
        weights: веса (О, М, П). (1, 4, 1) — классический PERT; наборы (1, 3, 2)
            и (1, 2, 3) в отчёте нужны, чтобы показать, как вес пессимистической
            оценки двигает дату окончания.

    Returns:
        Ожидаемая длительность в днях (дробная — округляется вызывающим).
    """
    a, b, c = weights
    return (a * o + b * m + c * p) / (a + b + c)


def with_pert_durations(project: Project, weights=(1, 4, 1)) -> Project:
    """Копия проекта, где длительности заменены ожидаемыми по PERT (округление до часа).

    Исходный проект не мутируется; подменяются только листовые задачи с
    оценками — вехи и фазы остаются как есть.
    """
    import copy
    p = copy.deepcopy(project)
    for t in p.leaf_tasks:
        if t.pert and not t.milestone:
            # Округление до часа (1/8 дня) держит длительность на часовой сетке
            # календаря 08–12/13–17: 4.6667 дн. в MS Project выглядит как
            # «4,67 дн.» и расходится со значением в поле Длительность4, а
            # часовые значения (4.5, 5.0) открываются как есть.
            t.dur_days = round(pert_days(*t.pert, weights=weights) * HOURS_PER_DAY) / HOURS_PER_DAY
    p.__post_init__()
    return p
