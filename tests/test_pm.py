"""Автопроверки учебного проекта: модель, покрытие требований ЛР, XML и совпадение с MPXJ.

Запуск: python -m pytest tests -q
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pm import analysis, cpm, model  # noqa: E402
from pm import paths  # noqa: E402  — единый источник путей и имён (T07)

P = model.load(paths.PROJECT_YAML)


# ---------- модель ----------

def test_no_cycles_and_known_predecessors():
    cpm.topo_order(P)   # бросает исключение при цикле или неизвестном ключе


def test_unique_keys_and_names():
    assert len({t.key for t in P.tasks}) == len(P.tasks)
    assert len({t.name for t in P.tasks}) == len(P.tasks), "имена задач используются для сопоставления в XML"


def test_every_work_task_has_resources_and_codes():
    for t in P.leaf_tasks:
        if t.milestone:
            assert not t.res, f"{t.wbs}: у вехи не должно быть ресурсов"
            continue
        assert t.res, f"{t.wbs} без ресурсов"
        assert t.code, f"{t.wbs} без кода работ"
        top, sub = t.code.split(".")
        assert sub in P.work_codes[top]["children"], t.code
        for rk in t.res:
            P.resource(rk)


def test_resource_dept_codes_valid():
    for r in P.resources:
        if r.dept:
            top, sub = r.dept.split(".")
            assert sub in P.dept_codes[top]["children"], r.dept


def test_pert_estimates_ordered():
    for t in P.leaf_tasks:
        o, m, p = t.pert
        assert o <= m <= p, t.wbs
        if not t.milestone:
            assert m == t.dur_days, f"{t.wbs}: наиболее вероятная оценка должна совпадать с длительностью"


# ---------- покрытие требований методички ----------

def test_lab_requirements_covered():
    leaves = P.leaf_tasks
    assert len([t for t in leaves if not t.milestone]) >= 10          # ЛР2: ≥10 задач
    assert sum(t.milestone for t in leaves) >= 3                        # ЛР1–2: вехи
    types = {ln.type for t in leaves for ln in t.links}
    assert {"FS", "SS", "FF"} <= types                                  # ЛР2: разные типы связей
    assert any(ln.lag_days for t in leaves for ln in t.links)           # запаздывание
    assert any(t.constraint for t in leaves)                            # ЛР2: ограничение
    assert any(t.deadline for t in leaves)                              # ЛР2: крайний срок
    assert len(P.exceptions()) >= 3                                     # ЛР1: нерабочие периоды
    kinds = {r.type for r in P.resources}
    assert kinds == {"work", "material", "cost"}                        # ЛР3: типы ресурсов
    assert len(P.resource("PM").availability) == 3                      # ЛР3 з.2: доступность
    assert any(r.rate_b for r in P.resources)                           # ЛР5: таблица B
    assert any(r.rate_change for r in P.resources)                      # ЛР5 з.2: дата действия
    assert any(t.fixed_cost for t in leaves)                            # ЛР5 з.6
    assert any(t.note for t in leaves) and any(t.link_url for t in leaves)  # ЛР4
    assert len(P.work_codes) >= 2 and all(v["children"] for v in P.work_codes.values())  # ЛР9 з.9


def test_overallocation_exists_for_labs_6_7():
    s, cal = cpm.schedule(P)
    over = cpm.overallocations(P, s, cal)
    assert len(over) >= 3, "для ЛР6–7 нужна перегрузка нескольких ресурсов"


def test_critical_path_is_continuous_chain():
    s, _ = cpm.schedule(P)
    crit = cpm.critical_keys(P, s)
    assert crit[0] == "kick" and crit[-1] == "m_done"
    assert len(crit) >= 8


def test_crash_scenarios_behave_as_lab_expects():
    res = analysis.crash_scenarios(P)
    base = res[0][1]
    assert all(d < base for _, d, _ in res[1:4]), "каждый способ сокращения должен дать эффект"
    shifted, fixed = res[4][1], res[5][1]
    deadline = dt.datetime.combine(P.task("m_done").deadline, dt.time(17))
    assert shifted > deadline >= fixed


def test_pert_weights_monotonic():
    _, fins = analysis.pert_table(P)
    assert fins[(1, 4, 1)] < fins[(1, 3, 2)] < fins[(1, 2, 3)]
    assert fins["p=m"] < fins[(1, 4, 1)]


def test_costs_sum_and_manual_example():
    s, cal = cpm.schedule(P)
    c = cpm.costs(P, s, cal)
    # 1.1 «Первое заседание оргкомитета»: 8 ч × (1200 + 1000) ₽/ч
    assert c["kick"]["total"] == 8 * (1200 + 1000)
    # 3.1 «Подбор зала»: BE 32 ч × 1100 + фикс. 50 000 (начисление в начале)
    assert c["venue"]["total"] == 32 * 1100 + 50000
    # 4.1 «Создание сайта»: UX 48 ч × 900
    assert c["website"]["total"] == 48 * 900
    phases, total, by_code, _, _ = analysis.cost_summary(P)
    assert abs(sum(by_code.values()) - total) < 1e-6


# ---------- XML через MPXJ (нужна Java) ----------

mpxj_ok = True
try:
    import jpype  # noqa: F401
    import mpxj  # noqa: F401
except Exception:  # pragma: no cover
    mpxj_ok = False
needs_java = pytest.mark.skipif(not mpxj_ok, reason="нет MPXJ/JPype")


def _ms_tasks(f):
    return {str(t.getName()): t for t in f.getTasks() if t.getName() is not None}


def _to_py(ldt):
    return dt.datetime(ldt.getYear(), ldt.getMonthValue(), ldt.getDayOfMonth(), ldt.getHour(), ldt.getMinute())


@needs_java
@pytest.mark.parametrize("weights", [None, (1, 4, 1), (1, 2, 3)])
def test_own_cpm_matches_mpxj_microsoft_scheduler(weights, tmp_path):
    from pm import msproject as ms
    p = model.with_pert_durations(P, weights) if weights else P
    f = ms.read(ms.write(ms.build(p), tmp_path / "x.xml", p))   # полный цикл: построить → XML → прочитать
    got = _ms_tasks(f)
    s, cal = cpm.schedule(p)
    for t in p.tasks:
        x = s[t.key]
        exp_start = cal.finish_dt(x.es) if t.milestone else cal.start_dt(x.es)
        assert _to_py(got[t.name].getStart()) == exp_start, f"{t.wbs} начало"
        assert _to_py(got[t.name].getFinish()) == cal.finish_dt(x.ef), f"{t.wbs} окончание"
        if not t.summary:
            assert bool(got[t.name].getCritical()) == (x.slack <= 1e-9), f"{t.wbs} критичность"


@needs_java
def test_full_xml_roundtrip_fields(tmp_path):
    from pm import msproject as ms
    f = ms.read(ms.write(ms.build(P, pert_fields=True), tmp_path / "full.xml", P))
    got = _ms_tasks(f)
    assert len(got) == len(P.tasks)   # суммарную задачу проекта MS Project создаёт сам
    for t in P.leaf_tasks:
        g = got[t.name]
        assert abs(g.getDuration().getDuration() - t.dur_days) < 1e-9, t.wbs
        assert str(g.getWBS()) == t.wbs
        assert (g.getOutlineCode(1) and str(g.getOutlineCode(1))) == t.code, t.wbs
        preds = sorted(str(r.getPredecessorTask().getName()) for r in g.getPredecessors())
        assert preds == sorted(P.task(ln.pred).name for ln in t.links), t.wbs
        if t.pert and not t.milestone:
            assert [g.getDuration(i).getDuration() for i in (1, 2, 3)] == list(t.pert), t.wbs
        if t.fixed_cost:
            assert float(g.getFixedCost()) == t.fixed_cost
        if t.constraint:
            assert str(g.getConstraintType()) == "START_NO_EARLIER_THAN"
        if t.deadline:
            assert g.getDeadline() is not None
    res = {str(r.getName()): r for r in f.getResources() if r.getName() is not None}
    assert set(res) == {r.name for r in P.resources}
    pm = res["Иванов И.И."]
    assert pm.getAvailability().size() == 3
    assert str(pm.getOutlineCode(1)) == "ОРГ.КООРД"
    assert float(pm.getCostRateTable(1).get(0).getStandardRate().getAmount()) == 1400
    aliases = {str(c.getAlias()) for c in f.getCustomFields() if c.getAlias()}
    assert {"Код работ", "Код отделов", "Оптимистическая длительность"} <= aliases
    cal = f.getDefaultCalendar()
    assert cal.getCalendarExceptions().size() == len(P.exceptions())


@needs_java
def test_fixed_cost_on_venue(tmp_path):
    """Аренда зала (50 000 ₽) — FixedCost задачи 3.1, а не назначение затратного ресурса."""
    from pm import msproject as ms
    f = ms.read(ms.write(ms.build(P), tmp_path / "full.xml", P))
    venue = next(t for t in f.getTasks() if t.getName() == "Подбор зала и технического оборудования")
    assert float(venue.getFixedCost()) == 50000
    res = {str(r.getName()): r for r in f.getResources() if r.getName() is not None}
    assert "Аренда зала и техники" in res


@needs_java
def test_built_files_are_wellformed_mspdi():
    import xml.etree.ElementTree as ET
    out = paths.OUT
    files = sorted(out.glob("*.xml"))
    if not files:
        pytest.skip("сначала запустите python build.py")
    for fp in files:
        root = ET.parse(fp).getroot()
        assert root.tag == "{http://schemas.microsoft.com/project}Project", fp.name
        # порядок верхнего уровня как в XSD: Calendars → Tasks → Resources → Assignments
        tags = [c.tag.split("}")[1] for c in root]
        order = [tags.index(x) for x in ("Calendars", "Tasks", "Resources", "Assignments") if x in tags]
        assert order == sorted(order), fp.name


# ---------- отчёт ----------

def test_shot_ids_unique_and_stable():
    from pm import report
    ids = [s["id"] for s in report.shots(P)]
    assert len(ids) == len(set(ids)) == 22
    assert ids[0] == "lr1_01" and ids[-1] == "lr9_03"


# ---------- манифест путей и имён (T07) ----------

def test_deliverables_match_manifest():
    """Каждый файл paths.MANIFEST существует в out/ (генерируется build.py).

    XML-варианты требуют Java (MPXJ/JPype); если их нет (не запускали сборку с JVM),
    тест пропускается. Их отсутствие фиксирует отдельный test_xml_saveversion_is_14."""
    for dirp, name in paths.MANIFEST:
        p = dirp / name
        if not p.is_file() and name.endswith(".xml"):
            pytest.skip(f"нет {name} — запустите python build.py с Java (MPXJ)")
        assert p.is_file(), f"нет файла манифеста: {p} — запустите python build.py"


# ---------- зависимости и версия пакета (T08) ----------

def _pyproject_data():
    import tomllib
    with open(HERE / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _dep_name(entry: str) -> str:
    import re
    m = re.match(r"([A-Za-z0-9_.-]+)", entry)
    assert m, f"не удалось извлечь имя пакета из: {entry!r}"
    return m.group(1).casefold()


def _dep_names(entries) -> set[str]:
    return {_dep_name(e) for e in entries}


def test_requirements_match_pyproject():
    data = _pyproject_data()
    in_pyproject = (_dep_names(data["project"]["dependencies"])
                    | _dep_names(data["project"]["optional-dependencies"]["dev"]))
    req = (HERE / "requirements.txt").read_text(encoding="utf-8")
    names = {_dep_name(line) for line in req.splitlines()
             if line and not line.startswith("#")}
    assert names, "requirements.txt не содержит пакетов"
    assert names == in_pyproject, (
        "requirements.txt рассинхронизирован с pyproject.toml: "
        f"в requirements лишние {names - in_pyproject}, в pyproject нет {in_pyproject - names}"
    )


def test_version_matches_pyproject():
    import pm
    data = _pyproject_data()
    assert pm.__version__ == data["project"]["version"], (
        "pm.__version__ и pyproject [project].version должны быть синхронизированы"
    )


# ---------- детерминизм и SaveVersion (T09) ----------

def test_xml_saveversion_is_14():
    """MPXJ 16.10 пишет <SaveVersion>14</SaveVersion> и для SaveVersion.Project2016 (enum 2010/2013/2016
    = 14, T09). Формат 14 — общий для MS Project 2010/2013/2016, 365 открывает."""
    import re
    xml_path = paths.OUT / paths.XML_PLAN
    if not xml_path.exists():
        pytest.skip("нет XML — запустите python build.py")
    xml = xml_path.read_text(encoding="utf-8")
    m = re.search(r"<SaveVersion>(\d+)</SaveVersion>", xml)
    assert m and m.group(1) == "14", "ожидается SaveVersion=14 (= MPXJ-семантика Project2016)"


@needs_java
def test_build_deterministic(tmp_path):
    """Два независимых прогона build.py дают байт-в-байт одинаковый out/ (T09):
    XML/expected.json/analysis.md — побайтово; .docx — по содержимому частей zip (python-docx
    кладёт в архив текущее время, см. S11 «docx исключить из diff»). Стабильность достигается
    пином версий и детерминированными GUID кодов структуры (msproject._lookup, T09)."""
    import hashlib
    import subprocess
    import zipfile
    dirs = [tmp_path / "a", tmp_path / "b"]
    for d in dirs:
        r = subprocess.run([sys.executable, "build.py", "--out", str(d)],
                           cwd=HERE, capture_output=True, text=True)
        assert r.returncode == 0, f"build.py --out {d} упал:\n{r.stderr[-2000:]}"

    def digest(root):
        out = {}
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix == ".docx":
                with zipfile.ZipFile(p) as z:
                    out[str(p.relative_to(root))] = dict(sorted(
                        (i.filename, hashlib.sha256(z.read(i.filename)).hexdigest())
                        for i in z.infolist()))
            else:
                out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    assert digest(dirs[0]) == digest(dirs[1]), "два прогона сборки различаются"


# ---------- ссылки: project.yaml / out/ → реальные пути репозитория ----------

REPO_ROOT = HERE                                 # тулкит лежит в корне репозитория
REPO_URL = "https://github.com/kadeom/project-management/"


def _repo_path(url: str) -> Path | None:
    """Путь в клоне по ссылке на этот репозиторий; None — внешняя или нераспознанная ссылка."""
    if not url.startswith(REPO_URL):
        return None
    parts = url[len(REPO_URL):].split("/", 2)            # <blob|tree>/main/<путь>
    if len(parts) < 3 or parts[0] not in ("blob", "tree") or parts[1] != "main":
        return None
    return REPO_ROOT / parts[2]


def test_project_yaml_links_point_to_existing_paths():
    """Каждая ссылка `link:` на этот репозиторий ведёт на существующий файл или каталог.

    Ловит дрейф после переименований: битая ссылка уходит в XML и в отчёт,
    и её замечает только преподаватель."""
    urls = [t.link_url for t in P.tasks if t.link_url]
    assert urls, "в плане есть задачи с гиперссылками (ЛР4)"
    checked = 0
    for url in urls:
        target = _repo_path(url)
        if target is None:
            continue
        checked += 1
        rel = target.relative_to(REPO_ROOT)
        assert target.exists(), f"битая ссылка в project.yaml: {url} → нет {rel}"
    assert checked >= 1, "ссылок на репозиторий в плане должно быть несколько"


def test_analysis_md_links_exist_and_match_model():
    """out/analysis.md: ссылки ведут на существующие пути и не отстают от project.yaml.

    Свежесть документа проверяется без Java и без пересборки: закоммиченный отчёт
    обязан содержать все ссылки текущей модели."""
    md_path = paths.OUT / paths.ANALYSIS_MD
    if not md_path.exists():
        pytest.skip("нет analysis.md — запустите python build.py")
    text = md_path.read_text(encoding="utf-8")
    urls = set(re.findall(r"https://github\.com/kadeom/project-management/[^\s|)]+", text))
    model_urls = {t.link_url for t in P.tasks
                  if t.link_url and t.link_url.startswith(REPO_URL)}
    assert model_urls <= urls, \
        "analysis.md устарел относительно project.yaml — пересобери: python build.py"
    for url in urls:
        target = _repo_path(url)
        assert target is not None and target.exists(), f"битая ссылка в analysis.md: {url}"


def test_xml_hyperlinks_point_to_existing_paths():
    """Гиперссылки в закоммиченных XML ведут на существующие пути (проверка без Java)."""
    for name in paths.XML_VARIANTS:
        xml_path = paths.OUT / name
        if not xml_path.exists():
            continue
        text = xml_path.read_text(encoding="utf-8")
        for url in re.findall(r"<HyperlinkAddress>([^<]+)</HyperlinkAddress>", text):
            target = _repo_path(url)
            if target is None:
                continue
            assert target.exists(), f"битая ссылка в {name}: {url}"


def test_jvm_missing_gives_actionable_error(monkeypatch):
    """Без Java падаем с подсказкой (default-jre / JAVA_HOME), а не с JVMNotFoundException.

    JPype при отсутствии JVM перечисляет перебранные каталоги и не говорит, что делать."""
    if not mpxj_ok:
        pytest.skip("нет JPype")
    import jpype
    from pm import msproject

    def boom(*args, **kwargs):
        raise jpype.JVMNotFoundException("no JVM found")

    monkeypatch.setattr(msproject, "_started", False)
    monkeypatch.setattr(jpype, "isJVMStarted", lambda: False)
    monkeypatch.setattr(jpype, "startJVM", boom)
    with pytest.raises(RuntimeError) as ei:
        msproject.jvm()
    msg = str(ei.value)
    assert "default-jre" in msg and "JAVA_HOME" in msg
