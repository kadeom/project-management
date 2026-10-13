"""Единый источник истины (SSOT) для путей и канонических имён артефактов ЛР MS Project.

Все скрипты тулкита — build.py и тесты — берут пути и имена ТОЛЬКО отсюда (T07):
ни один канонический файл (XML-варианты, expected.json, analysis.md, отчёт .docx)
не должен иметь собственный литерал в схеме ниже.

Пути намеренно HERE-относительные: тулкит работает прямо из клона без установки
(PyPA «run from source»; см. build.py).

MANIFEST — исчерпывающий перечень закоммиченных артефактов в out/; тест
test_deliverables_match_manifest сверяет его с содержимым каталога.
"""
from __future__ import annotations

from pathlib import Path

# ---------- каталоги ----------

PACKAGE_ROOT = Path(__file__).resolve().parents[1]   # корень репозитория
OUT = PACKAGE_ROOT / "out"                           # генерирует build.py (XML, expected.json, analysis.md, .docx)
AUTOMATION = PACKAGE_ROOT / "automation"             # UI-автоматизация MS Project (скриншоты, fill_report)
RESULTS = AUTOMATION / "results"                     # runtime-результаты automation/ (gitignore)
SHOTS = RESULTS / "shots"                            # PNG-скриншоты lrN_KK для вставки в отчёт

PROJECT_YAML = PACKAGE_ROOT / "project.yaml"

# ---------- артефакты в out/ (build.py) ----------

XML_PLAN = "01_plan_LR1-2.xml"
XML_FULL = "02_full_LR3-7_9.xml"
XML_FULL_SAFE = "02_full_safe.xml"
XML_PERT_IN = "03_pert_input_LR8.xml"
XML_PERT_OUT = "04_pert_result_LR8.xml"
XML_VARIANTS = [XML_PLAN, XML_FULL, XML_FULL_SAFE, XML_PERT_IN, XML_PERT_OUT]

# .mpp — проприетарный бинарь MS Project; создаётся scripts/xml_to_mpp.py из XML
# через COM-автоматизацию (нужен установленный MS Project). Закоммичены для удобства:
# студент открывает .mpp напрямую, без ручного импорта XML.
MPP_VARIANTS = [name.replace(".xml", ".mpp") for name in XML_VARIANTS]

EXPECTED_JSON = "expected.json"
ANALYSIS_MD = "analysis.md"
REPORT_DOCX = "Отчёт_ЛР_MS_Project.docx"              # заготовка из report.docx (build.py)
REPORT_READY_DOCX = "Отчёт_ЛР_MS_Project_готовый.docx"  # после вставки скриншотов (automation/fill_report.py)

# .mpp, который пересобирает automation/ms_project_ui.py (lr9_02 → lr9_03): в нём
# добавлены настраиваемые поля «Общая стоимость» / «% от общей стоимости». Лежит в
# RESULTS (не в out/): это runtime-артефакт, а не канонический MANIFEST.
MPP_LR9_COSTS = "09_costs_LR9.mpp"

# ---------- манифест: исчерпывающий перечень канонических файлов ----------

MANIFEST: list[tuple[Path, str]] = [
    # build.py → out/
    (OUT, XML_PLAN), (OUT, XML_FULL), (OUT, XML_FULL_SAFE), (OUT, XML_PERT_IN), (OUT, XML_PERT_OUT),
    (OUT, EXPECTED_JSON), (OUT, ANALYSIS_MD), (OUT, REPORT_DOCX),
]
