#!/usr/bin/env python3
"""Скриншоты ручных шагов ЛР1–9 в MS Project (Windows, COM, RU-интерфейс).

    py -m pip install '.[automation]'          # pywin32, pywinauto, psutil, pillow
    py -m automation.ms_project_ui shots        # все 22 снимка lrN_KK
    py -m automation.ms_project_ui shots --only lr3_01,lr7_02

Результат: automation/results/shots/<id>.png (+ <id>_a/_b для «до/после») и
automation/results/run_log.json. После снимков вставьте их в отчёт:

    py -m automation.fill_report

ID скриншота совпадают с метками в out/Отчёт_ЛР_MS_Project.docx
(см. pm/report.py::SHOT_MARK и shots()). Модель задач — project.yaml (KONF-2026).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import threading
import time
import traceback
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # run-from-source: корень репозитория
from pm import paths  # noqa: E402

OUT, RES, SHOTS = paths.OUT, paths.RESULTS, paths.SHOTS
PLAN = paths.XML_PLAN
FULL = paths.XML_FULL
PERT_IN = paths.XML_PERT_IN

VIEWS = {
    "gantt": ["Диаграмма Ганта", "Gantt Chart"],
    "res_sheet": ["Лист ресурсов", "Resource Sheet"],
    "task_usage": ["Использование задач", "Task Usage"],
    "res_usage": ["Использование ресурсов", "Resource Usage"],
    "res_graph": ["График ресурсов", "Resource Graph"],
    "level_gantt": ["Диаграмма Ганта с выравниванием", "Leveling Gantt"],
}
TABLES = {"cost": ["Затраты", "Cost"]}
FILTERS = {
    "critical": ["Критические", "Критические задачи", "Critical"],
    "overalloc": ["Ресурсы с превышением доступности", "Превышение доступности", "Overallocated Resources"],
}
F = {"Cost1": 188743786, "Cost2": 188743787, "Number1": 188743767, "Number2": 188743768,
     "Number3": 188743769, "Duration1": 188743783, "Duration2": 188743784, "Duration3": 188743785,
     "Duration4": 188743955, "OutlineCode1": 188744096}

try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


class MSP:
    def __init__(self):
        import win32com.client as w
        self.w = w
        last = None
        for attempt in range(5):
            try:
                self.app = w.gencache.EnsureDispatch("MSProject.Application")
                break
            except Exception as e:
                last = e
                time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"MS Project не поднялся за 5 попыток: {last!r}")
        self.c = w.constants
        self.app.Visible = True
        self.app.DisplayAlerts = False
        self.dismiss_startup_prompts()
        self.log: list[dict] = []

    # ---------- файлы ----------
    def open(self, name: str, ro: bool = True):
        while self.app.Projects.Count:
            self.app.FileCloseEx(self.c.pjDoNotSave)
        path = OUT / name
        kw = {"ReadOnly": True} if ro else {}
        self.app.FileOpenEx(Name=str(path), **kw)
        try:
            self.app.AppMaximize()
        except Exception:
            pass
        return self.app.ActiveProject

    def save_mpp(self, name: str) -> Path:
        RES.mkdir(parents=True, exist_ok=True)
        dst = RES / (Path(name).stem + ".mpp")
        self.app.FileSaveAs(Name=str(dst), FormatID="MSProject.mpp")
        return dst

    # ---------- навигация ----------
    def _first_ok(self, fn, names):
        last = None
        for n in names:
            try:
                fn(n)
                return n
            except Exception as e:
                last = e
        raise RuntimeError(f"ни одно имя не подошло: {names}: {last}")

    SCREENS = {"res_sheet": "pjResourceSheet", "task_usage": "pjTaskUsage",
               "res_usage": "pjResourceUsage", "res_graph": "pjResourceGraph", "gantt": "pjGantt"}

    def view(self, key):
        try:
            return self._first_ok(lambda n: self.app.ViewApply(Name=n), VIEWS[key])
        except RuntimeError:
            if key not in self.SCREENS:
                raise
            screen = getattr(self.c, self.SCREENS[key])
            for v in self.app.ActiveProject.Views:
                if v.Screen == screen:
                    self.app.ViewApply(Name=v.Name)
                    return v.Name
            raise

    def table(self, key):
        try:
            return self._first_ok(lambda n: self.app.TableApply(Name=n), TABLES[key])
        except RuntimeError:
            for t in self.app.ActiveProject.TaskTables:
                if any(t.Name.startswith(n[:5]) for n in TABLES[key]):
                    self.app.TableApply(Name=t.Name)
                    return t.Name
            raise

    def filter(self, key, highlight=False):
        return self._first_ok(lambda n: self.app.FilterApply(Name=n, Highlight=highlight), FILTERS[key])

    def zoom_all(self):
        try:
            self.app.ZoomTimescale(Entire=True)
        except Exception:
            pass

    def task(self, name):
        for t in self.app.ActiveProject.Tasks:
            if t is not None and t.Name == name:
                return t
        raise KeyError(name)

    def resource(self, name):
        for r in self.app.ActiveProject.Resources:
            if r is not None and r.Name == name:
                return r
        raise KeyError(name)

    def select_task(self, name):
        self.app.EditGoTo(ID=self.task(name).ID)

    def select_resource_row(self, name):
        self.app.SelectRow(Row=self.resource(name).ID, RowRelative=False)

    def make_table(self, name: str, field_ids: list[int], widths=None):
        names = [self.app.FieldConstantToFieldName(f) for f in field_ids]
        widths = widths or [40 if i == 0 else 14 for i in range(len(names))]
        self.app.TableEditEx(Name=name, TaskTable=True, Create=True, OverwriteExisting=True,
                             FieldName=names[0], Width=widths[0], ShowInMenu=True)
        for n, w in zip(names[1:], widths[1:], strict=True):
            self.app.TableEditEx(Name=name, TaskTable=True, NewFieldName=n, Width=w)
        self.app.TableApply(Name=name)

    def select_tab(self, dlg, title: str):
        from pywinauto import Desktop
        w = Desktop(backend="uia").window(handle=dlg)
        w.child_window(title=title, control_type="TabItem").select()

    # ---------- скриншоты ----------
    def _winproj_pid(self):
        import win32process
        h = self._find_winproj_hwnd()
        if h:
            try:
                return win32process.GetWindowThreadProcessId(h)[1]
            except Exception:
                pass
        try:
            import psutil
            for p in psutil.process_iter(["name"]):
                try:
                    if (p.info.get("name") or "").lower() == "winproj.exe":
                        return p.pid
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _find_winproj_hwnd(self):
        import win32gui
        main = None

        def cb(hwnd, _):
            nonlocal main
            try:
                if (main is None and win32gui.IsWindowVisible(hwnd)
                        and win32gui.GetClassName(hwnd) == "JWinproj-WhimperMainClass"):
                    main = hwnd
            except Exception:
                pass

        win32gui.EnumWindows(cb, None)
        return main

    def grab(self, sid: str, suffix: str = "", foreground=False):
        from PIL import ImageGrab
        SHOTS.mkdir(parents=True, exist_ok=True)
        time.sleep(1.2)
        bbox = None
        if not foreground:
            try:
                import win32gui
                hwnd = self._find_winproj_hwnd()
                if hwnd:
                    self._force_foreground(hwnd)
                    bbox = win32gui.GetWindowRect(hwnd)
                    import win32api
                    win32api.SetCursorPos(((bbox[0] + bbox[2]) // 2, bbox[1] + 12))
                    time.sleep(0.8)
            except Exception:
                bbox = None
        self._hide_tooltips()
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        path = SHOTS / f"{sid}{('_' + suffix) if suffix else ''}.png"
        img.save(path)
        return path

    def _hide_tooltips(self):
        try:
            import win32con
            import win32gui
            import win32process
            pid = self._winproj_pid()
            if pid is None:
                return

            def cb(h, _):
                if (win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) in ("tooltips_class32", "SysShadow")
                        and win32process.GetWindowThreadProcessId(h)[1] == pid):
                    win32gui.ShowWindow(h, win32con.SW_HIDE)
            win32gui.EnumWindows(cb, None)
            time.sleep(0.3)
        except Exception:
            pass

    @staticmethod
    def _force_foreground(hwnd):
        import win32api
        import win32gui
        import win32process
        try:
            fg = win32gui.GetForegroundWindow()
            if fg == hwnd:
                return
            cur = win32api.GetCurrentThreadId()
            tgt = win32process.GetWindowThreadProcessId(fg)[0] if fg else cur
            if tgt != cur:
                win32process.AttachThreadInput(cur, tgt, True)
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if tgt != cur:
                    win32process.AttachThreadInput(cur, tgt, False)
        except Exception:
            pass

    def _winproj_dialogs(self):
        import win32gui
        import win32process
        pid = self._winproj_pid()
        if pid is None:
            return []
        out = []

        def cb(h, _):
            cls = win32gui.GetClassName(h)
            if (win32gui.IsWindowVisible(h) and (cls == "#32770" or (cls.startswith("JWinproj-") and cls != "JWinproj-WhimperMainClass"))
                    and win32process.GetWindowThreadProcessId(h)[1] == pid):
                out.append(h)
        win32gui.EnumWindows(cb, None)
        return out

    def dismiss_startup_prompts(self, timeout=20.0):
        import win32con
        import win32gui
        BUTTONS = ("Нет", "Отмена", "No", "Cancel", "Пропустить", "Skip")

        def _click_button(box):
            clicked = False

            def cb(b, _):
                nonlocal clicked
                try:
                    if win32gui.GetClassName(b) == "Button":
                        txt = win32gui.GetWindowText(b).strip()
                        if txt and any(tx in txt for tx in BUTTONS):
                            win32gui.SendMessage(b, win32con.BM_CLICK, 0, 0)
                            clicked = True
                except Exception:
                    pass
            win32gui.EnumChildWindows(box, cb, None)
            return clicked

        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                _ = self.app.Projects.Count   # лёгкий вызов: работает — сервер свободен
                break
            except Exception:
                pass
            boxes = self._winproj_dialogs()
            if not boxes:
                time.sleep(0.4)
                continue
            for b in list(boxes):
                try:
                    if not _click_button(b):
                        win32gui.PostMessage(b, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
                        win32gui.PostMessage(b, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
                        time.sleep(0.3)
                        if win32gui.IsWindow(b) and win32gui.IsWindowVisible(b):
                            win32gui.PostMessage(b, win32con.WM_CLOSE, 0, 0)
                except Exception:
                    pass
            time.sleep(0.5)

    def dialog_shot(self, sid: str, open_dialog, wait=2.5, keys=None):
        def worker():
            import win32con
            import win32gui
            from PIL import ImageGrab
            dlg = None
            for _ in range(int(wait * 10) + 50):
                time.sleep(0.1)
                ds = self._winproj_dialogs()
                if ds:
                    dlg = ds[0]
                    break
            if not dlg:
                return
            try:
                time.sleep(0.8)
                self._force_foreground(dlg)
                time.sleep(0.5)
                if keys:
                    keys(dlg)
                    time.sleep(0.8)
                SHOTS.mkdir(parents=True, exist_ok=True)
                try:
                    ImageGrab.grab(bbox=win32gui.GetWindowRect(dlg), all_screens=True).save(SHOTS / f"{sid}.png")
                except Exception as e:
                    print(f"[dialog_shot] {sid}: захват упал ({e}) — диалог всё равно закрываю", flush=True)
            finally:
                import win32api
                try:
                    self._force_foreground(dlg)
                except Exception:
                    pass
                try:
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
                    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
                except Exception:
                    pass
                time.sleep(1.0)
                try:
                    if win32gui.IsWindow(dlg) and win32gui.IsWindowVisible(dlg):
                        win32gui.PostMessage(dlg, win32con.WM_CLOSE, 0, 0)
                except Exception:
                    pass
        hw = self._find_winproj_hwnd()
        if hw:
            self._force_foreground(hw)
        th = threading.Thread(target=worker, daemon=True)
        th.start()
        try:
            open_dialog()
        except Exception:
            pass
        th.join(timeout=wait + 15)
        for _ in range(20):
            try:
                self.app.DisplayAlerts = False
                break
            except Exception:
                time.sleep(0.5)
        if not (SHOTS / f"{sid}.png").exists():
            raise RuntimeError("скриншот диалога не получен")

    # ---------- жизненный цикл ----------
    def quit(self):
        try:
            self.app.Quit(self.c.pjDoNotSave)
        except Exception:
            try:
                self.app.Quit()
            except Exception:
                pass

    def wait_ready(self, sec=10):
        for _ in range(sec * 2):
            try:
                _ = self.app.Projects.Count
                return
            except Exception:
                time.sleep(0.5)
        import psutil
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower() == "winproj.exe":
                p.kill()
        time.sleep(3)
        self.app = self.w.gencache.EnsureDispatch("MSProject.Application")
        self.app.Visible = True
        self.app.DisplayAlerts = False

    def step(self, sid, fn):
        self.wait_ready()
        t0 = time.time()
        try:
            info = fn() or {}
            self.log.append({"id": sid, "ok": True, "sec": round(time.time() - t0, 1), **info})
            print(f"  ✓ {sid}")
        except Exception as e:
            self.log.append({"id": sid, "ok": False, "error": repr(e), "trace": traceback.format_exc()})
            print(f"  ✗ {sid}: {e!r}")

    def dump_log(self):
        RES.mkdir(parents=True, exist_ok=True)
        log_path = RES / "run_log.json"
        prev = []
        if log_path.exists():
            try:
                prev = json.loads(log_path.read_text(encoding="utf-8"))
                if not isinstance(prev, list):
                    prev = []
            except Exception:
                prev = []
        stamp = dt.datetime.now().isoformat(timespec="seconds")
        for e in self.log:
            e.setdefault("ts", stamp)
        log_path.write_text(json.dumps(prev + self.log, ensure_ascii=False, indent=2), encoding="utf-8")


def shot_steps(m: MSP) -> dict:
    """ID скриншота → функция. ID совпадают с метками в отчёте (pm/report.py::shots)."""

    def set_formula(field, candidates, check):
        for formula in candidates:
            try:
                m.app.CustomFieldSetFormula(FieldID=F[field], Formula=formula)
                m.app.CustomFieldPropertiesEx(FieldID=F[field], Attribute=m.c.pjFieldAttributeFormula,
                                              SummaryCalc=m.c.pjCalcNone)
                m.app.CalculateProject()
                if not check():
                    continue
            except Exception:
                continue
            stored = m.app.CustomFieldGetFormula(FieldID=F[field])
            if not stored:
                raise RuntimeError(f"CustomFieldGetFormula вернул пусто для {field}")
            return {"set": formula, "stored": str(stored)}
        raise RuntimeError(f"формула для {field} не дала ожидаемого значения: {candidates}")

    def lr1_01():
        m.open(PLAN)
        m.dialog_shot("lr1_01", lambda: m.app.ProjectSummaryInfo())

    def lr1_02():
        m.open(PLAN)
        m.dialog_shot("lr1_02", lambda: m.app.ChangeWorkingTime())

    def lr2_01():
        m.open(PLAN)
        m.view("gantt")
        m.app.OptionsViewEx(ProjectSummary=True)
        m.zoom_all()
        m.grab("lr2_01")

    def lr2_02():
        m.open(PLAN)
        m.view("gantt")
        t = m.task("Создание сайта конференции")
        t.Duration = t.Duration + 3 * 480
        m.select_task("Конференция завершена")   # веха с крайним сроком — виден индикатор
        m.app.GotoTaskDates()
        m.grab("lr2_02")

    def lr3_01():
        m.open(FULL)
        m.view("res_sheet")
        m.grab("lr3_01")

    def lr3_02():
        m.open(FULL)
        m.view("res_sheet")
        m.select_resource_row("Иванов И.И.")
        m.dialog_shot("lr3_02", lambda: m.app.InformationDialog())

    def lr3_03():
        m.open(FULL)
        t = m.task("Организация кофе-брейков и обеда")
        for a in t.Assignments:
            a.WorkContour = m.c.pjFrontLoaded
        m.view("task_usage")
        m.select_task("Организация кофе-брейков и обеда")
        m.grab("lr3_03")

    def lr4_01():
        m.open(FULL)
        m.dialog_shot("lr4_01", lambda: m.app.WBSCodeMaskEdit())

    def lr4_02():
        m.open(FULL)
        m.view("gantt")
        m.select_task("Первое заседание оргкомитета")
        m.dialog_shot("lr4_02", lambda: m.app.InformationDialog(), keys=lambda h: m.select_tab(h, "Заметки"))

    def lr4_03():
        m.open(FULL)
        m.view("gantt")
        m.select_task("Определение тематики и целевой аудитории")
        m.grab("lr4_03")

    def lr5_01():
        m.open(FULL)
        m.view("gantt")
        m.table("cost")
        m.select_task("Подбор зала и технического оборудования")   # фикс. затраты 50 000 ₽
        m.app.GotoTaskDates()
        m.grab("lr5_01")

    def lr5_02():
        m.open(FULL)
        m.view("task_usage")
        m.table("cost")
        m.app.DetailStylesRemoveAll()
        m.app.DetailStylesAdd(Item=1)          # 1 = «Затраты»
        m.select_task("Организация кофе-брейков и обеда")
        m.app.GotoTaskDates()
        m.grab("lr5_02")

    def lr6_01():
        m.open(FULL)
        m.view("res_sheet")
        m.filter("overalloc")
        m.grab("lr6_01")

    def lr6_02():
        m.open(FULL)
        m.view("res_sheet")
        m.select_resource_row("Смирнова А.В.")
        m.view("res_graph")
        m.app.GotoNextOverAllocation()
        m.grab("lr6_02")

    def lr6_03():
        m.open(FULL)
        m.view("res_usage")
        m.grab("lr6_03")

    def lr7_01():
        m.open(FULL)
        m.dialog_shot("lr7_01", lambda: m.app.LevelingOptions())

    def lr7_02():
        m.open(FULL)
        m.view("level_gantt")
        m.zoom_all()
        for r in m.app.ActiveProject.Resources:
            if r is not None and r.Type == m.c.pjResourceTypeWork:
                r.CanLevel = True
        m.app.LevelingOptionsEx(Automatic=False, PeriodBasis=m.c.pjDayByDay, DelayInSlack=False)
        m.app.LevelNow(All=True)
        delayed = next((t.Name for t in m.app.ActiveProject.Tasks
                        if t is not None and not t.Summary and float(t.LevelingDelay) > 0), None)
        m.app.LevelingClear(All=True)
        if delayed:
            m.select_task(delayed)
        m.grab("lr7_02", "a")
        m.app.LevelNow(All=True)
        if delayed:
            m.select_task(delayed)
        m.grab("lr7_02", "b")

    def lr8_01():
        m.open(PERT_IN, ro=False)
        m.view("gantt")
        m.app.CustomFieldRename(FieldID=F["Duration4"], NewName="Ожидаемая по PERT")
        # Подбор зала: О=3, М=4, П=6 → (3+16+6)/6 = 25/6 ≈ 4.167 дн. = 2000 мин
        t = m.task("Подбор зала и технического оборудования")
        formula = set_formula("Duration4", ["([Длительность1]+4*[Длительность2]+[Длительность3])/6",
                                            "([Duration1]+4*[Duration2]+[Duration3])/6"],
                              lambda: abs(float(t.Duration4) - (3 + 4 * 4 + 6) / 6 * 480) < 1)
        m.app.CustomFieldRename(FieldID=F["Number2"], NewName="Стоимость основного ресурса")
        cost_formula = set_formula("Number2", ["[Затраты1]*[Число1]", "[Cost1]*[Number1]"],
                                   lambda: abs(float(t.Number2) - float(t.Cost1) * float(t.Number1)) < 0.01)
        c = m.c
        m.make_table("ЛР8 PERT", [c.pjTaskName, c.pjTaskDuration, F["Duration1"], F["Duration2"],
                                  F["Duration3"], F["Duration4"]], widths=[30, 11, 13, 13, 13, 14])
        m.select_task("Подбор зала и технического оборудования")
        m.grab("lr8_01")
        m.save_mpp(PERT_IN)
        return {"pert_formula": formula, "cost_formula": cost_formula}

    def lr8_02():
        for name, suf in ((PERT_IN, "a"), (paths.XML_PERT_OUT, "b")):
            m.open(name)
            m.view("gantt")
            m.zoom_all()
            m.grab("lr8_02", suf)

    def lr9_01():
        m.open(FULL)
        m.view("gantt")
        m.app.GanttBarStyleCritical(Show=True)
        m.zoom_all()
        m.grab("lr9_01", "a")
        m.filter("critical")
        m.grab("lr9_01", "b")

    def lr9_02():
        m.open(FULL)
        m.view("gantt")
        total = float(m.app.ActiveProject.ProjectSummaryTask.Cost)
        m.app.CustomFieldRename(FieldID=F["Cost2"], NewName="Общая стоимость")
        for t in m.app.ActiveProject.Tasks:
            if t is not None:
                t.Cost2 = total
        m.app.CustomFieldRename(FieldID=F["Number3"], NewName="% от общей стоимости")
        t = m.task("Подбор зала и технического оборудования")
        pct_formula = set_formula("Number3", ["100*[Затраты]/[Затраты2]", "100*[Cost]/[Cost2]"],
                                  lambda: abs(float(t.Number3) - 100 * float(t.Cost) / total) < 0.01)
        m.app.CustomFieldPropertiesEx(FieldID=F["Number3"], Attribute=m.c.pjFieldAttributeFormula,
                                      SummaryCalc=m.c.pjCalcFormula)
        c = m.c
        m.make_table("ЛР9 Затраты", [c.pjTaskName, c.pjTaskCost, F["Cost2"], F["Number3"], F["OutlineCode1"]])
        m.grab("lr9_02")
        m.save_mpp(paths.MPP_LR9_COSTS)
        return {"pct_formula": pct_formula}

    def lr9_03():
        m.open(RES / paths.MPP_LR9_COSTS)
        m.view("gantt")
        m.app.CustomFieldPropertiesEx(FieldID=F["Number3"], Attribute=m.c.pjFieldAttributeFormula,
                                      SummaryCalc=m.c.pjCalcRollupSum)
        m.app.TableApply(Name="ЛР9 Затраты")
        m.app.OptionsViewEx(DisplaySummaryTasks=False)
        grp = m.app.ActiveProject.TaskGroups.Add("Код работ", m.app.FieldConstantToFieldName(F["OutlineCode1"]))
        grp.ShowSummary = True
        m.app.GroupApply(Name="Код работ")
        m.grab("lr9_03")

    return {k: v for k, v in locals().items() if k.startswith("lr")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["shots"], default="shots", nargs="?")
    ap.add_argument("--only", help="ID скриншотов через запятую")
    a = ap.parse_args()
    m = MSP()
    try:
        steps = shot_steps(m)
        only = set(a.only.split(",")) if a.only else None
        for sid, fn in steps.items():
            if only is None or sid in only:
                m.step(sid, fn)
    finally:
        m.dump_log()
        try:
            while m.app.Projects.Count:
                m.app.FileCloseEx(m.c.pjDoNotSave)
            m.quit()
        except Exception:
            pass
    crashed = [x["id"] for x in m.log if not x["ok"] and "error" in x]
    if crashed:
        print(f"\nупавшие шаги: {crashed} — см. automation/results/run_log.json")
        sys.exit(1)
    print(f"\nготово: {len(m.log)} шаг(ов); снимки в {SHOTS}")


if __name__ == "__main__":
    main()
