"""Построение файла MS Project (MSPDI XML) через библиотеку MPXJ.

MPXJ (https://www.mpxj.org) — открытая библиотека, которая читает и пишет форматы
MS Project. Мы строим проект объектами MPXJ, рассчитываем даты её планировщиком
`org.mpxj.cpm.MicrosoftScheduler` (эмуляция алгоритма MS Project) и сохраняем
через `MSPDIWriter` — так кодировки полей XML берутся из библиотеки, а не пишутся
вручную. Полученный .xml MS Project 365 открывает через «Файл → Открыть».
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import jpype
import mpxj  # noqa: F401  (добавляет jar-файлы MPXJ в classpath)

from .model import Project

# «JVM уже поднимали»: jpype не позволяет остановить и перезапустить JVM в одном
# процессе, поэтому старт возможен только один раз — флаг живёт весь процесс.
_started = False


def _no_jvm_error() -> RuntimeError:
    """Подсказка вместо голого JVMNotFoundException от JPype.

    Ошибка JPype перечисляет перебранные каталоги и не говорит, что делать; на свежем
    Debian/без JAVA_HOME именно она и приходит первым сообщением пользователя."""
    return RuntimeError(
        "Java (JVM) не найдена: MPXJ работает через JVM. Поставьте JRE 8+ с разрядностью, "
        "равной разрядности Python (на Debian: apt install default-jre, либо temurin), "
        "либо задайте JAVA_HOME. Сверка версий: docs/reference/version-matrix.md"
    )


def jvm():
    """Поднять JVM один раз и вернуть корневой пакет org.mpxj для локальных импортов.

    Вызывается из всех функций, которым нужны классы MPXJ: повторный вызов
    дёшев (пакет уже подключён), а сама JVM стартует только если её ещё нет.
    """
    global _started
    if not _started:
        if not jpype.isJVMStarted():
            # -Dfile.encoding=UTF-8: имена задач, ресурсов и названия фаз на
            # русском — без явной кодировки JVM берёт default charset платформы
            # (на Windows это cp1251/cp1252) и сравнение строк ломается.
            # convertStrings=True: Java String приходят как str, иначе сравнение
            # «имя из MS» с Python-строкой в тестах всегда False.
            try:
                jpype.startJVM("-Dfile.encoding=UTF-8", convertStrings=True)
            except jpype.JVMNotFoundException:
                raise _no_jvm_error() from None
        _started = True
    import org.mpxj as m
    return m


def _ldt(d: dt.date, hour: int = 8):
    """date → java.time.LocalDateTime; 8:00 — первый слот календаря 08–12/13–17 (конец дня — 17, см. deadline)."""
    from java.time import LocalDateTime
    return LocalDateTime.of(d.year, d.month, d.day, hour, 0)


def _ld(d: dt.date):
    """date → java.time.LocalDate: для исключений календаря, где время не участвует."""
    from java.time import LocalDate
    return LocalDate.of(d.year, d.month, d.day)


# Коды связей и начисления затрат → enum MPXJ (названия читаются как в MS Project).
# ACCRUE: START/END/PRORATED = «в начале / в конце / пропорционально» (pjAccrueAt).
LINK = {"FS": "FINISH_START", "SS": "START_START", "FF": "FINISH_FINISH", "SF": "START_FINISH"}
ACCRUE = {"start": "START", "end": "END", "prorated": "PRORATED"}
# Ограничения MS Project: SN/FN — начало/окончание, E/L/T — «не раньше / не позже /
# ровно». cpm учитывает пока только SNET («Начало не ранее» — единственный тип в
# project.yaml); карта полная, чтобы выгрузка не падала, если в YAML появится
# новый тип ограничения.
CONSTRAINT = {"SNET": "START_NO_EARLIER_THAN", "SNLT": "START_NO_LATER_THAN",
              "FNET": "FINISH_NO_EARLIER_THAN", "FNLT": "FINISH_NO_LATER_THAN",
              "MSO": "MUST_START_ON", "MFO": "MUST_FINISH_ON"}

# Настраиваемые поля: (поле, псевдоним). Значения заполняются в build().
# Псевдоним — это имя поля, которое студент увидит в MS Project вместо «Затраты1»;
# DURATION1–3 в паре с pert_fields (иначе алиас скрыт: в файле без PERT поле
# было бы пустым и лишь засоряло список полей).
TASK_ALIASES = {
    "COST1": "Ставка основного ресурса",
    "NUMBER1": "Часы основного ресурса",
    "DURATION1": "Оптимистическая длительность",
    "DURATION2": "Ожидаемая длительность",
    "DURATION3": "Пессимистическая длительность",
    "TEXT1": "Ответственный",
    "OUTLINE_CODE1": "Код работ",
}
RES_ALIASES = {"OUTLINE_CODE1": "Код отделов", "TEXT1": "Должность"}


def _lookup(cf, field, codes: dict, next_id: list, seed: str):
    """Таблица подстановки для кода структуры: 2 уровня, разделитель «.».

    Значения уходят в XML вместе с описанием — MS Project показывает их в
    диалоге «Определение кода» и в поле задачи/ресурса. `next_id` — счётчик ID
    значений, общий для двух таблиц (работы и отделы): он передаётся списком,
    чтобы вложенная item() делила состояние с вызывающим.
    """
    import java.util.UUID as UUID
    from org.mpxj import CustomFieldValueDataType, CustomFieldValueMask
    from org.mpxj.mpp import CustomFieldValueItem
    field_def = cf.getOrCreate(field)
    table = field_def.getLookupTable()
    # Детерминированный GUID: UUID.randomUUID() давал новый GUID на каждый прогон →
    # XML с кастомными полями был невоспроизводим (T-009). nameUUIDFromBytes — стабилен
    # для одинакового seed и валиден форматом (MSPDI-схема, xsd:string; MS Project при
    # импорте GUID не требует конкретных значений — валидировано по learn.microsoft.com).
    guid = UUID.nameUUIDFromBytes(f"pm-labs:{seed}".encode("utf-8"))
    table.setGUID(guid)
    table.setShowIndent(True)
    masks = field_def.getMasks()
    for level in (1, 2):
        masks.add(CustomFieldValueMask(0, level, ".", CustomFieldValueDataType.TEXT))

    def item(value, desc, parent=None):
        next_id[0] += 1
        it = CustomFieldValueItem(Integer(next_id[0]))
        it.setValue(value)
        it.setDescription(desc)
        it.setType(CustomFieldValueDataType.TEXT)
        it.setGUID(guid)
        if parent is not None:
            it.setParentUniqueID(Integer(parent))
        table.add(it)
        cf.registerValue(it)
        return next_id[0]

    from java.lang import Integer
    for code, spec in codes.items():
        pid = item(code, spec["name"])
        for sub, desc in spec.get("children", {}).items():
            item(sub, desc, pid)


def build(project: Project, *, with_resources: bool = True, with_extras: bool = True,
          pert_fields: bool = False, title_suffix: str = ""):
    """Создать org.mpxj.ProjectFile из модели проекта и рассчитать расписание.

    Даты считает штатный MicrosoftScheduler MPXJ (эмуляция алгоритма MS
    Project), а не наш cpm — это намеренно два независимых расчёта, их
    согласованность проверяют тесты. Запись в файл — отдельно, через write().

    Args:
        with_resources: выгрузить ресурсы, ставки, доступность и назначения;
            False — для плана без ресурсов (ЛР1–2).
        with_extras: заметки, гиперссылки, настраиваемые поля и таблицы кодов;
            False даёт запасной файл на случай, если MS Project откажется
            открывать настраиваемые поля.
        pert_fields: заполнить поля Длительность1–3 тремя PERT-оценками (ЛР8).
        title_suffix: прибавка к названию проекта (вариант выгрузки «PERT 1-4-1»).

    Returns:
        Проект MPXJ, готовый к записи через write().
    """
    m = jvm()
    from java.lang import Double, Integer  # noqa: F401
    from org.mpxj import (AccrueType, Availability, ConstraintType, CostRateTable,
                          CostRateTableEntry, Duration, ProjectFile, Rate, Relation,
                          RelationType, ResourceField, ResourceType, TaskField,
                          TaskType, TimeUnit)
    from org.mpxj.common import LocalDateTimeHelper
    from org.mpxj.cpm import MicrosoftScheduler

    f = ProjectFile()
    props = f.getProjectProperties()
    meta = project.meta
    props.setProjectTitle(meta["name"] + title_suffix)
    props.setName(meta["short"])
    props.setAuthor(meta.get("author"))
    props.setCompany(meta.get("company"))
    props.setStartDate(_ldt(project.start))
    props.setCurrencySymbol(meta.get("currency", "₽"))
    props.setCurrencyCode(meta.get("currency_code", "RUB"))
    props.setSymbolPosition(m.CurrencySymbolPosition.AFTER_WITH_SPACE)  # «100 ₽»: символ после суммы
    props.setCurrencyDigits(Integer(2))
    # Границы рабочего дня в «Сведениях о проекте»: 08:00–17:00 при календаре
    # 08–12 и 13–17 (обед задаёт календарь, а не эти поля).
    props.setDefaultStartTime(__import__("java.time", fromlist=["LocalTime"]).LocalTime.of(8, 0))
    props.setDefaultEndTime(__import__("java.time", fromlist=["LocalTime"]).LocalTime.of(17, 0))
    # Автопланирование: иначе MS Project помечает задачи как «вручную» и при
    # открытии перестаёт учитывать связи и ограничения.
    props.setNewTasksAreManual(False)
    # Суммарная задача проекта в списке задач: приём методички (Формат →
    # «Суммарная задача проекта»), без флага MS не покажет её при открытии.
    props.setShowProjectSummaryTask(True)

    cal = f.addDefaultBaseCalendar()
    cal.setName(project.calendar.get("name", "Стандартный"))
    f.setDefaultCalendar(cal)
    props.setDefaultCalendar(cal)
    # Нерабочие периоды (праздники, каникулы) — как исключения календаря: MS
    # сам применит их ко всем задачам, даты в моделях уже посчитаны без них.
    for a, b, name in project.exceptions():
        ex = cal.addCalendarException(_ld(a), _ld(b))
        ex.setName(name)

    # --- ресурсы ---
    resources = {}
    if with_resources:
        for r in project.resources:
            x = f.addResource()
            x.setName(r.name)
            x.setType({"work": ResourceType.WORK, "material": ResourceType.MATERIAL,
                       "cost": ResourceType.COST}[r.type])
            if r.initials:
                x.setInitials(r.initials)
            if r.group:
                x.setGroup(r.group)
            if r.type == "material":
                x.set(ResourceField.MATERIAL_LABEL, r.label or "шт.")
            if r.type == "work":
                # MaxUnits — в процентах (MPXJ): 100 = полная загрузка. Держим 100 %
                # у всех: снижение на период задаётся таблицей Availability (см. ниже),
                # а не понижением максимума — иначе MS считал бы лимит дважды.
                x.set(ResourceField.MAX_UNITS, Double(100.0))
                # Пропорциональное начисление трудозатрат — режим по умолчанию;
                # у фиксированных затрат задачи свой режим (accrual из модели).
                x.setAccrueAt(AccrueType.PRORATED)
                if r.role:
                    x.setText(1, r.role)
                if r.dept and with_extras:
                    x.setOutlineCode(1, r.dept)
            if r.type != "cost":
                # Затратный ресурс ставок не имеет — его сумма приходит из назначения.
                start, end = LocalDateTimeHelper.START_DATE_NA, LocalDateTimeHelper.END_DATE_NA
                table_a = CostRateTable()
                std = Rate(float(r.rate), TimeUnit.HOURS)
                ot = Rate(float(r.ot), TimeUnit.HOURS)
                if r.rate_change:
                    # Смена ставки по дате — это две строки таблицы A: до даты
                    # действия и после (MS хранит «Затраты за использование» в
                    # той же строке, поэтому она продублирована в обеих).
                    ch = _ldt(r.rate_change["from"])
                    new = Rate(float(r.rate_change["rate"]), TimeUnit.HOURS)
                    table_a.add(CostRateTableEntry(start, ch, Double(r.per_use), [std, ot]))
                    table_a.add(CostRateTableEntry(ch, end, Double(r.per_use), [new, ot]))
                else:
                    table_a.add(CostRateTableEntry(start, end, Double(r.per_use), [std, ot]))
                # Индекс 0 — таблица A; в project.yaml для B одна ставка на весь
                # период, поэтому таблица B (индекс 1) пишется одной строкой.
                x.setCostRateTable(0, table_a)
                if r.rate_b is not None:
                    table_b = CostRateTable()
                    table_b.add(CostRateTableEntry(start, end, Double(r.per_use),
                                                   [Rate(float(r.rate_b), TimeUnit.HOURS), ot]))
                    x.setCostRateTable(1, table_b)
            for av in r.availability:
                # Единицы доступности: в модели доли (0.5 = 50 %), у MPXJ —
                # проценты, поэтому ×100. Окно до 17:00 последнего дня, чтобы
                # день «по» ещё попал в период; без даты окончания — бессрочно.
                s_ = _ldt(av["from"], 8)
                e_ = _ldt(av["to"], 17) if av["to"] else LocalDateTimeHelper.END_DATE_NA
                x.getAvailability().add(Availability(s_, e_, Double(av["units"] * 100)))
            resources[r.key] = x

    # --- задачи ---
    tasks = {}
    parents = {}
    for t in project.tasks:
        if t.level == 1:
            x = f.addTask()
        else:
            parent_key = next(p.key for p in project.tasks if t.key in p.children)
            x = parents[parent_key].addTask()
        x.setName(t.name)
        x.setWBS(t.wbs)
        if t.summary:
            parents[t.key] = x
        else:
            # Фиксированные единицы — тип по умолчанию MS Project и тот, что
            # разбирают в ЛР3 (длительность меняется не сама).
            x.setType(TaskType.FIXED_UNITS)
            x.setDuration(Duration.getInstance(Double(t.dur_days), TimeUnit.DAYS))
            # Задача не начата: пройденная часть нулевая, остаток равен полной
            # длительности, иначе MS показывает частичное выполнение.
            x.setActualDuration(Duration.getInstance(Double(0.0), TimeUnit.DAYS))
            x.setRemainingDuration(Duration.getInstance(Double(t.dur_days), TimeUnit.DAYS))
            x.setPercentageComplete(Double(0.0))
            x.setMilestone(t.milestone)
            if t.constraint:
                x.setConstraintType(getattr(ConstraintType, CONSTRAINT[t.constraint["type"]]))
                x.setConstraintDate(_ldt(t.constraint["date"]))
            if t.deadline:
                # Крайний срок — конец рабочего дня (17:00), как его трактует MS.
                x.setDeadline(_ldt(t.deadline, 17))
            if t.fixed_cost:
                x.setFixedCost(Double(t.fixed_cost))
                x.setFixedCostAccrual(getattr(AccrueType, ACCRUE[t.accrual]))
        if with_extras:
            if t.note:
                x.setNotes(t.note)
            if t.link_url:
                x.setHyperlink("Материалы проекта на GitHub")
                x.setHyperlinkAddress(t.link_url)
            if t.code:
                x.setOutlineCode(1, t.code)
        if pert_fields and t.pert and not t.summary:
            # Поля Длительность1–3 = О/М/П (нумерация custom-полей с единицы —
            # так они и выглядят в MS Project). Длительность4 в отчёте ЛР8
            # заполняется формулой вручную: формулы в XML не переносятся.
            o, ml, p = t.pert
            for i, v in ((1, o), (2, ml), (3, p)):
                x.setDuration(i, Duration.getInstance(Double(v), TimeUnit.DAYS))
        tasks[t.key] = x

    for t in project.leaf_tasks:
        for ln in t.links:
            # Лаг передаём в днях: MPXJ сам переведёт его в LinkLag (десятые
            # доли минуты) при записи MSPDI, руками минуты считать не нужно.
            b = (Relation.Builder().predecessorTask(tasks[ln.pred]).successorTask(tasks[t.key])
                 .type(getattr(RelationType, LINK[ln.type]))
                 .lag(Duration.getInstance(Double(ln.lag_days), TimeUnit.DAYS)))
            tasks[t.key].addPredecessor(b)

    # --- назначения ---
    if with_resources:
        for t in project.leaf_tasks:
            # «Основной» ресурс задачи — тот, что даёт больше всего трудозатрат:
            # его ставка, часы и имя уходят в настраиваемые поля «Ставка основного
            # ресурса», «Часы основного ресурса», «Ответственный» (ЛР5/ЛР9).
            hours_main, main = 0.0, None
            for rk, u in t.res.items():
                r = project.resource(rk)
                a = tasks[t.key].addResourceAssignment(resources[rk])
                if r.type == "work":
                    # Трудозатраты = длительность × единицы (8 ч/дн — как в
                    # model.HOURS_PER_DAY). setUnits, как и MaxUnits, у MPXJ
                    # хранится в процентах, поэтому доли 0.5 уходят как 50.
                    hrs = t.dur_days * 8 * u
                    a.setUnits(Double(u * 100))
                    a.setWork(Duration.getInstance(Double(hrs), TimeUnit.HOURS))
                    a.setRemainingWork(Duration.getInstance(Double(hrs), TimeUnit.HOURS))
                    a.setActualWork(Duration.getInstance(Double(0.0), TimeUnit.HOURS))
                    if hrs > hours_main:
                        hours_main, main = hrs, r
                elif r.type == "material":
                    # Единицы материала — количество (200 листов), а не проценты
                    # загрузки, поэтому setUnits без ×100.
                    a.setUnits(Double(u))
                    a.setWork(Duration.getInstance(Double(u), TimeUnit.HOURS))
                    a.setRemainingWork(Duration.getInstance(Double(u), TimeUnit.HOURS))
                    a.setActualWork(Duration.getInstance(Double(0.0), TimeUnit.HOURS))
                else:
                    a.setCost(Double(u))
                    # без RemainingCost MS Project при импорте пересчитывает Cost
                    # (NOTES.md, п.2: 18 000 ₽ превращались в 80 000 ₽)
                    a.setRemainingCost(Double(u))
                    # Затраты не измеряются часами: иначе MS показывает
                    # трудозатраты там, где ресурс их не имеет.
                    a.setActualCost(Double(0.0))
                    a.setActualWork(Duration.getInstance(Double(0.0), TimeUnit.HOURS))
                    a.setWork(Duration.getInstance(Double(0.0), TimeUnit.HOURS))
                    a.setRemainingWork(Duration.getInstance(Double(0.0), TimeUnit.HOURS))
            if main is not None and with_extras:
                tasks[t.key].setCost(1, Double(main.rate))
                tasks[t.key].setNumber(1, Double(hours_main))
                tasks[t.key].setText(1, main.name)

    # --- псевдонимы настраиваемых полей ---
    cf = f.getCustomFields()
    if with_extras:
        for name, alias in TASK_ALIASES.items():
            if name.startswith("DURATION") and not pert_fields:
                # PERT-поля заводим только в PERT-выгрузках: в остальных файлах
                # они были бы пустыми и лишь засоряли список полей MS Project.
                continue
            cf.getOrCreate(getattr(TaskField, name)).setAlias(alias)
        if with_resources:
            for name, alias in RES_ALIASES.items():
                cf.getOrCreate(getattr(ResourceField, name)).setAlias(alias)

    if with_extras:
        # ID значений кодов структуры попадают в XML, поэтому старт фиксирован
        # (детерминизм выгрузки), а счётчик один на обе таблицы — чтобы
        # ValueID задач и ресурсов не пересекались внутри файла.
        next_id = [1000]
        _lookup(cf, TaskField.OUTLINE_CODE1, project.work_codes, next_id, "work-codes")
        if with_resources:
            _lookup(cf, ResourceField.OUTLINE_CODE1, project.dept_codes, next_id, "dept-codes")

    # Учёт ограничений включаем явно: от него зависит, применит ли MS «Начало не
    # ранее» к расписанию (то же правило, что в cpm.schedule). Даты «сегодня»
    # привязаны к началу проекта, чтобы в файле не мелькала реальная текущая дата.
    props.setHonorConstraints(True)
    props.setCurrentDate(_ldt(project.start))
    props.setStatusDate(_ldt(project.start))
    # Финальный пересчёт дат штатным планировщиком MPXJ — эмуляцией MS Project.
    # Он обязателен перед записью: иначе MS при открытии пересчитает файл
    # по-своему, и даты разойдутся с out/expected.json.
    MicrosoftScheduler().schedule(f, _ldt(project.start))
    return f


# Пространство имён MSPDI — то, что пишет MSPDIWriter. ElementTree регистрирует
# его с пустым префиксом (см. _link_outline_codes): без этого повторная запись
# дала бы префиксы ns0: вместо безымянного xmlns, как в выгрузке MS Project.
NS = "http://schemas.microsoft.com/project"
# FieldID настраиваемых полей для ссылки «задача → значение кода структуры»:
# 188744096 — Код работ (задача), 205521174 — Код отделов (ресурс); взяты из
# FieldTypeHelper MPXJ и совпадают с тем, что пишет MSPDIWriter.
TASK_OC1, RES_OC1 = "188744096", "205521174"


def write(f, path: str | Path, project: Project | None = None) -> Path:
    """Сохранить MSPDI XML. Если передан project — проставить значения кодов структуры.

    Каталог создаётся при необходимости; `project` нужен, чтобы после записи
    дописать ссылки задач/ресурсов на значения кодов (MPXJ их не пишет).

    Returns:
        Путь к записанному файлу.
    """
    from org.mpxj.mspdi import MSPDIWriter, SaveVersion
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = MSPDIWriter()
    # Явно фиксируем намерение: Project2016 в терминах MPXJ пишет `<SaveVersion>14</SaveVersion>`
    # (enum SaveVersion: Project2010/2013/2016 = 14 — это и есть дефолт writer, см. T-009). Формат 14
    # открывается MS Project 2010/2013/2016 (общий формат файлов); 365 — тоже. Вариантам «9/12»
    # здесь места нет, поэтому флаг только документирует поведение, а не меняет его.
    writer.setSaveVersion(SaveVersion.Project2016)
    writer.write(f, str(path))
    if project is not None:
        _link_outline_codes(path, project)
    return path


def _link_outline_codes(path: Path, project: Project) -> None:
    """MPXJ пишет таблицу подстановки кода структуры, но не ссылку задачи на значение
    (<ValueID>). Проставляем её сами: путь «РАЗ.FE» → ValueID листового значения."""
    # Парсим собственный вывод build.py (out/), а не недоверенный ввод → defusedxml не требуется (T-036).
    import xml.etree.ElementTree as ET  # nosec B405
    ET.register_namespace("", NS)
    q = lambda tag: f"{{{NS}}}{tag}"  # noqa: E731
    tree = ET.parse(path)  # nosec B314
    root = tree.getroot()
    paths: dict[str, dict[str, str]] = {}
    codes = root.find(q("OutlineCodes"))
    if codes is None:
        return
    for oc in codes.findall(q("OutlineCode")):
        vals = {v.findtext(q("ValueID")): v for v in oc.iter(q("Value")) if v.find(q("ValueID")) is not None}

        def full(v, vals=vals):  # B023: явно связываем vals текущей итерации
            parent = v.findtext(q("ParentValueID"))
            own = v.findtext(q("Value"))
            return own if not parent else full(vals[parent]) + "." + own
        paths[oc.findtext(q("FieldID"))] = {full(v): vid for vid, v in vals.items()}

    wanted = {("Task", t.name): (TASK_OC1, t.code) for t in project.tasks if t.code}
    wanted.update({("Resource", r.name): (RES_OC1, r.dept) for r in project.resources if r.dept})
    for kind in ("Task", "Resource"):
        for el in root.iter(q(kind)):
            key = (kind, el.findtext(q("Name")))
            if key not in wanted:
                continue
            fid, code = wanted[key]
            for oc in el.findall(q("OutlineCode")):
                if oc.findtext(q("FieldID")) == fid and oc.find(q("ValueID")) is None:
                    ET.SubElement(oc, q("ValueID")).text = paths[fid][code]
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def read(path: str | Path):
    """Прочитать файл проекта любым форматом MPXJ (наш MSPDI XML, .mpp и др.).

    Поднимает JVM при необходимости. Так выгрузка проверяется «в обратную
    сторону»: тесты читают записанный XML и сверяют его с моделью.
    """
    from org.mpxj.reader import UniversalProjectReader
    jvm()
    return UniversalProjectReader().read(str(path))
