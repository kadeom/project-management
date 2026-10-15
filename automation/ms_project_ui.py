#!/usr/bin/env python3
"""Скриншоты ручных шагов ЛР1–9 в MS Project (Windows, COM, RU-интерфейс).

    py -m pip install '.[automation]'          # pywin32, pywinauto, psutil, pillow
    py -m automation.ms_project_ui shots        # все 22 снимка lrN_KK
    py -m automation.ms_project_ui shots --only lr3_01,lr7_02

Результат: automation/results/shots/<id>.png (+ <id>_a/_b для «до/после») и
automation/results/run_log.json. После снимков вставьте их в отчёт:

    py -m automation.fill_report

ID скриншота совпадают с метками в отчёте
(см. pm/report.py::SHOT_MARK и shots(); ДЗ — pm/report_szi.py::shot_ids, шаги
szi_shot_steps, ID вида v12_01/v10_01). Модель задач — project.yaml (KONF-2026).
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
    def fit_window(self, w: int = 2920, h: int = 1010):
        """Фиксированный размер окна 2920×1010 (штатный ~1920×1080 + запас).

        AppMaximize в портретном разрешении экрана сжимает окно до ~1100 px:
        диаграмма «прилипает» к 1984 г. и не восстанавливается даже
        GotoTaskDates/ZoomTimescale. Окно шире экрана допустимо:
        SWP_NOSENDCHANGING обходит WM_GETMINMAXINFO, а PrintWindow рисует
        и ушедшую за край часть. Вызывается до FileOpenEx."""
        import ctypes
        import time as _t

        import win32con
        import win32gui
        hwnd = self._find_winproj_hwnd()
        if not hwnd:
            return
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        _t.sleep(0.6)
        try:
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, w, h,
                                              0x0002 | 0x0010 | 0x0400)
        except Exception:
            pass
        _t.sleep(0.6)

    def open(self, name: str, ro: bool = True):
        while self.app.Projects.Count:
            self.app.FileCloseEx(self.c.pjDoNotSave)
        path = OUT / name
        kw = {"ReadOnly": True} if ro else {}
        self.fit_window()                    # до открытия; AppMaximize не использовать
        self.app.FileOpenEx(Name=str(path), **kw)
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

    @staticmethod
    def _msp_uncovered(hwnd, bbox) -> bool:
        """Истинно, если в центре окна действительно MS Project, а не чужое окно сверху."""
        import win32gui
        try:
            pt = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
            w = win32gui.WindowFromPoint(pt)
            if not w:
                return False
            return win32gui.GetAncestor(w, 2) == hwnd   # GA_ROOT
        except Exception:
            return True   # проверить не смогли — не блокируем снимок

    def grab(self, sid: str, suffix: str = "", foreground=False):
        from PIL import ImageGrab
        SHOTS.mkdir(parents=True, exist_ok=True)
        time.sleep(1.2)
        path = SHOTS / f"{sid}{('_' + suffix) if suffix else ''}.png"
        hwnd = None if foreground else self._find_winproj_hwnd()
        try:
            bbox = None
            if not foreground:
                import win32gui
                if not hwnd:
                    raise RuntimeError("окно MS Project не найдено")
                for _ in range(5):
                    self._force_foreground(hwnd)
                    time.sleep(0.5)
                    bbox = win32gui.GetWindowRect(hwnd)
                    if self._msp_uncovered(hwnd, bbox):
                        break
                else:
                    raise RuntimeError("окно MS Project перекрыто другим окном")
                import win32api
                try:
                    win32api.SetCursorPos(((bbox[0] + bbox[2]) // 2, bbox[1] + 12))
                    time.sleep(0.8)
                except Exception:
                    pass   # сеанс заблокирован — ввод недоступен, не мешаем
                if not self._msp_uncovered(hwnd, bbox):
                    raise RuntimeError("окно MS Project перекрыто другим окном")
            self._hide_tooltips()
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception as e:
            # сеанс заблокирован (GetDC экрана падает) или окно перекрыто:
            # читаем содержимое самого окна через PrintWindow — чужое окно
            # на снимок не попадёт, DWM-часть рисует само приложение
            if not hwnd:
                raise
            print(f"[grab] {sid}: экранный захват недоступен ({e}) — PrintWindow",
                  flush=True)
            self._hide_tooltips()
            img = _printwindow(hwnd)
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


def _mk_table(m: MSP, name: str, field_ids: list[int], widths: list[int],
              aligns: list[int] | None = None, wrap: list[bool] | None = None):
    """Явное создание таблицы задач и её применение.

    Встроенные таблицы («Запись», «Затраты») в XML-проектах ДЗ теряют колонки —
    поэтому таблицу собираем с нуля: Create=True + OverwriteExisting + TableApply.

    Align: 0 — pjLeft, 1 — pjCenter, 2 — pjRight (по умолчанию у MSP pjRight,
    поэтому имя задачи задаём слева явно). ShowAddNewColumn=False — убирает
    «Добавить новый столбец», который занимает ширину панели.
    (WrapText в этой версии MSP не применяется — колонки расширяем по контенту.)
    """
    app = m.app
    fn = [app.FieldConstantToFieldName(f) for f in field_ids]
    aligns = aligns or [0] * len(fn)
    wrap = wrap or [False] * len(fn)
    app.TableEditEx(Name=name, TaskTable=True, Create=True, OverwriteExisting=True,
                    FieldName=fn[0], Width=widths[0], Align=aligns[0], WrapText=wrap[0],
                    ShowInMenu=True, ShowAddNewColumn=False, AlignTitle=0,
                    HeaderTextWrap=True, HeaderAutoRowHeightAdjustment=True)
    for n in fn[1:]:
        app.TableEditEx(Name=name, TaskTable=True, NewFieldName=n, ShowAddNewColumn=False)
    # выравнивание/перенос/ширина применяются к FieldName — правим каждую колонку
    for n, w, a, wp in zip(fn, widths, aligns, wrap, strict=True):
        app.TableEditEx(Name=name, TaskTable=True, FieldName=n, Width=w, Align=a,
                        WrapText=wp, ShowAddNewColumn=False, AlignTitle=0,
                        HeaderTextWrap=True, HeaderAutoRowHeightAdjustment=True)
    app.TableApply(Name=name)


def _money_len(v) -> int:
    """Длина строки «1 583 370,00 сом» — для оценки ширины колонки затрат."""
    try:
        s = f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
    except Exception:
        return 10
    return len(s) + 4


def _content_widths(m: MSP, kinds: list[str], summary: bool = False) -> list[int]:
    """Ширины колонок по фактическому содержимому задач проекта (без обрезки).

    summary=True — учитываем сводную строку проекта (row 0): она выводится
    полужирным, поэтому её длина берётся с запасом ×1.30.
    """
    lens = {"id": 3, "name": 8, "dur": 12, "date": 12, "pred": 15,
            "fixed": 10, "cost": 10, "base": 10}
    money = {"fixed": lambda t: t.FixedCost,
             "cost": lambda t: t.Cost,
             "base": lambda t: t.BaselineCost}
    if summary and "name" in kinds:
        try:
            pst = m.app.ActiveProject.ProjectSummaryTask
            if pst is not None:
                lens["name"] = max(lens["name"], int(len(str(pst.Name)) * 1.30))
        except Exception:
            pass
    if set(kinds) & ({"name", "pred"} | set(money)):
        for t in m.app.ActiveProject.Tasks:
            if t is None:
                continue
            if "name" in kinds:
                lens["name"] = max(lens["name"], len(str(t.Name)))
            if "pred" in kinds:
                lens["pred"] = max(lens["pred"], len(str(t.Predecessors or "")))
            for k, get in money.items():
                if k in kinds:
                    lens[k] = max(lens[k], _money_len(get(t)))
    return [(lens[k] + 2 if k in ("name", "pred", "fixed", "cost", "base")
             else lens[k] + 1)
            for k in kinds]


def _ribbon_height(hwnd) -> int:
    """Высота ленты менеджера: 356 — развёрнута, 156 — свёрнута (только вкладки)."""
    import win32gui

    hs = []

    def cb(h, _):
        try:
            if (win32gui.GetClassName(h) == "MsoCommandBarDock"
                    and win32gui.IsWindowVisible(h)):
                r = win32gui.GetWindowRect(h)
                hs.append(r[3] - r[1])
        except Exception:
            pass
    win32gui.EnumChildWindows(hwnd, cb, None)
    return max(hs) if hs else 0


def _ribbon_min(m: MSP):
    """Свернуть ленту менеджера (Ctrl+F1) — на снимке больше строк задач.

    MSP запоминает состояние ленты между запусками, поэтому не переключаем
    вслепую, а проверяем высоту: сворачиваем только если она больше 250 px.
    """
    try:
        hwnd = m._find_winproj_hwnd()
        if not hwnd:
            return
        for _ in range(3):
            h = _ribbon_height(hwnd)
            if not h or h <= 250:
                return
            m._force_foreground(hwnd)
            time.sleep(0.4)
            import win32api
            import win32con
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x70, 0, 0, 0)
            time.sleep(0.15)
            win32api.keybd_event(0x70, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(1.0)
    except Exception:
        pass


def _printwindow(hwnd):
    """Захват окна через PrintWindow в DIB-секцию.

    Работает в заблокированном/отключённом сеансе, где GetDC(NULL) и
    ImageGrab недоступны; окно может быть частично за краем экрана —
    читается содержимое самого окна. Координаты физические: процесс
    делает SetProcessDPIAware при импорте модуля.
    """
    import ctypes

    from PIL import Image

    import win32gui

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    u32 = ctypes.windll.user32
    g32 = ctypes.windll.gdi32
    x0, y0, x1, y1 = win32gui.GetWindowRect(hwnd)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        raise RuntimeError(f"у окна MSP пустой rect {(x0, y0, x1, y1)}")
    hdc = u32.GetWindowDC(hwnd)
    mem = g32.CreateCompatibleDC(hdc)
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth, bmi.biHeight = w, -h     # top-down
    bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
    pbits = ctypes.c_void_p()
    hbmp = g32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(pbits), None, 0)
    if not hbmp:
        g32.DeleteDC(mem)
        u32.ReleaseDC(hwnd, hdc)
        raise RuntimeError("CreateDIBSection не создал битмап")
    g32.SelectObject(mem, hbmp)
    try:
        # PW_RENDERFULLCONTENT (Win 8.1+) — с содержимым DWM/Office;
        # flag=0 (WM_PRINT) как запасной вариант
        ok = u32.PrintWindow(hwnd, mem, 2) or u32.PrintWindow(hwnd, mem, 0)
        buf = ctypes.string_at(pbits.value, w * h * 4) if ok else b""
    finally:
        g32.DeleteObject(hbmp)
        g32.DeleteDC(mem)
        u32.ReleaseDC(hwnd, hdc)
    if not ok or len(buf) != w * h * 4:
        raise RuntimeError("PrintWindow не отрисовал окно MSP")
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)


def _widen_pane(m: MSP, chars: int, cap: float = 0.85):
    """Перетащить сплиттер «таблица | диаграмма» так, чтобы таблица шириной
    ~`chars` символов (18 px/символ, факт ~17.6 px/симв., + 60 px запас)
    встала без обрезки.

    Drag постится в окно сплиттера (WM_LBUTTONDOWN / WM_MOUSEMOVE /
    WM_LBUTTONUP) — работает и в заблокированном сеансе, где SetCursorPos
    недоступен; физический drag — запасной путь. После каждой попытки
    геометрия перечитывается (до 3 попыток); если так и не дотянули —
    RuntimeError (шаг помечен ✗, чем тихо обрезанная колонка).
    """
    import time as _t

    import win32gui
    import win32process

    WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE = 0x0201, 0x0202, 0x0200
    MK_LBUTTON = 0x0001
    need = int(chars * 18.0) + 60

    def measure():
        hwnd = m._find_winproj_hwnd()
        if not hwnd:
            return None, None, -1
        grids = []

        def cb(h, _):
            if win32gui.GetClassName(h) == "JWinproj-GridClass":
                grids.append(win32gui.GetWindowRect(h))
        win32gui.EnumChildWindows(hwnd, cb, None)
        if not grids:
            return hwnd, None, -1
        lg = min(grids, key=lambda g: g[2])   # левая таблица заканчивается раньше всех
        return hwnd, lg, lg[2] - win32gui.GetWindowRect(hwnd)[0]

    def _lparam(px, py):
        return (py << 16) | (px & 0xFFFF)

    def post_drag(hwnd, x, y, target):
        tgt = win32gui.WindowFromPoint((x, y))
        if tgt:
            try:
                if win32process.GetWindowThreadProcessId(tgt)[1] != m._winproj_pid():
                    tgt = None
            except Exception:
                tgt = None
        if not tgt:
            found = []

            def cb(h, _):
                if win32gui.GetClassName(h) == "JWinproj-WhimperClass":
                    found.append(h)
            win32gui.EnumChildWindows(hwnd, cb, None)
            tgt = found[0] if found else None
        if not tgt:
            return False
        left, top, right, bottom = win32gui.GetClientRect(tgt)
        sx, sy = win32gui.ClientToScreen(tgt, (0, 0))
        cx = max(0, min(right - 1, x - sx))
        cy = max(0, min(bottom - 1, y - sy))
        win32gui.PostMessage(tgt, WM_LBUTTONDOWN, MK_LBUTTON, _lparam(cx, cy))
        _t.sleep(0.2)
        dx = target - x
        for i in range(1, 26):
            win32gui.PostMessage(tgt, WM_MOUSEMOVE, MK_LBUTTON,
                                 _lparam(cx + dx * i // 25, cy))
            _t.sleep(0.05)
        win32gui.PostMessage(tgt, WM_LBUTTONUP, 0, _lparam(cx + dx, cy))
        _t.sleep(1.0)
        return True

    def physical_drag(x, y, target):
        import win32api
        import win32con

        win32api.SetCursorPos((x, y))
        _t.sleep(0.4)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        _t.sleep(0.25)
        for i in range(1, 21):
            win32api.SetCursorPos((x + (target - x) * i // 20, y))
            _t.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        _t.sleep(1.0)

    for _attempt in range(3):
        hwnd, lg, cur = measure()
        if hwnd is None or lg is None:
            return
        if cur >= need:                      # уже помещается
            return
        wr = win32gui.GetWindowRect(hwnd)
        frac = min(cap, (need + 80) / (wr[2] - wr[0]))
        target = wr[0] + int((wr[2] - wr[0]) * frac)
        # точка — на строке задач, не в шапке (иначе уедет на деление колонки)
        x, y = lg[2], lg[1] + max(70, (lg[3] - lg[1]) // 4)
        if target - x < 50:
            continue
        try:
            post_drag(hwnd, x, y, target)
        except Exception:
            pass
        if measure()[2] >= need:
            return
        try:                                  # запасной путь — физический drag
            physical_drag(x, y, target)
        except Exception:
            pass                              # сеанс заблокирован — ввода нет
        if measure()[2] >= need:
            return
    raise RuntimeError(f"сплиттер не дотянут: {measure()[2]} < {need} px")


def szi_shot_steps(m: MSP) -> dict:
    """Скриншоты практической работы (ДЗ): v12_* — PAM, v10_* — DLP+SIEM.

    ID совпадают с метками pm.report_szi.SHOT_MARK (szi_shot_ids) и с --only
    в main(). Один файл плана на вариант — XML_SZI_V12 / XML_SZI_V10.
    """
    def table_gantt():
        """Встроенная «Запись» в этих проектах теряет колонку «Название» —
        создаём явную таблицу ДЗ2 (Ид, Название, Длительность, Начало,
        Окончание); ширина колонок — по содержимому задач (без обрезки).
        «Предшественники» убран: у варианта 10 имя 78 символов + 17 символов
        предшественников не влезают в допустимую ширину таблицы. Сводная
        строка проекта (row 0, полужирная) учитывается с запасом ×1.30."""
        widths = _content_widths(m, ["id", "name", "dur", "date", "date"],
                                 summary=True)
        _mk_table(m, "ДЗ2",
                  [m.c.pjTaskID, m.c.pjTaskName, m.c.pjTaskDuration, m.c.pjTaskStart,
                   m.c.pjTaskFinish],
                  widths,
                  aligns=[2, 0, 0, 0, 0])
        _widen_pane(m, sum(widths))

    def table_cost():
        """Таблица «Затраты» тоже теряет колонки — собираем явно, ширина по
        контенту; фиксированные/базовые затраты считаются отдельно (обычно
        0,00 сом, а «Затраты» — реальные суммы до 16+ символов)."""
        widths = _content_widths(m, ["name", "fixed", "cost", "base"])
        _mk_table(m, "ДЗ3",
                  [m.c.pjTaskName, m.c.pjTaskFixedCost, m.c.pjTaskCost,
                   m.c.pjTaskBaselineCost],
                  widths,
                  aligns=[0, 2, 2, 2])
        _widen_pane(m, sum(widths))

    def steps(xml_name: str, prefix: str) -> dict:
        def gantt_01():
            m.open(xml_name)
            m.view("gantt")
            _ribbon_min(m)
            m.app.OptionsViewEx(ProjectSummary=True)   # до таблицы: widen — последним
            table_gantt()
            m.zoom_all()
            m.grab(f"{prefix}_01")

        def critical_02():
            m.open(xml_name)
            m.view("gantt")
            _ribbon_min(m)
            m.app.OptionsViewEx(ProjectSummary=True)   # как в кадре 01
            table_gantt()
            m.app.GanttBarStyleCritical(Show=True)
            m.zoom_all()
            m.grab(f"{prefix}_02", "a")
            m.filter("critical")
            m.grab(f"{prefix}_02", "b")

        def cost_03():
            m.open(xml_name)
            m.view("gantt")
            _ribbon_min(m)
            table_cost()
            m.zoom_all()
            m.grab(f"{prefix}_03")

        def overalloc_04():
            m.open(xml_name)
            m.view("res_sheet")
            _ribbon_min(m)
            m.filter("overalloc")
            m.grab(f"{prefix}_04")

        def usage_05():
            m.open(xml_name)
            m.view("res_usage")
            _ribbon_min(m)
            m.grab(f"{prefix}_05")

        return {f"{prefix}_01": gantt_01, f"{prefix}_02": critical_02,
                f"{prefix}_03": cost_03, f"{prefix}_04": overalloc_04,
                f"{prefix}_05": usage_05}

    out = {}
    out.update(steps(paths.XML_SZI_V12, "v12"))
    out.update(steps(paths.XML_SZI_V10, "v10"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["shots"], default="shots", nargs="?")
    ap.add_argument("--only", help="ID скриншотов через запятую")
    a = ap.parse_args()
    m = MSP()
    try:
        steps = {**shot_steps(m), **szi_shot_steps(m)}
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
