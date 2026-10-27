"""Единый источник истины (SSOT) для путей и канонических имён артефактов ЛР MS Project.

Все скрипты тулкита — build.py и тесты — берут пути и имена ТОЛЬКО отсюда (T-007):
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

PACKAGE_ROOT = Path(__file__).resolve().parents[2]   # корень репозитория (src/pm/paths.py → ../..)
OUT = PACKAGE_ROOT / "out"                           # генерирует build.py (XML, expected.json, analysis.md, .docx)
AUTOMATION = PACKAGE_ROOT / "automation"             # UI-автоматизация MS Project (скриншоты, fill_report)
RESULTS = AUTOMATION / "results"                     # runtime-результаты automation/ (gitignore)
SHOTS = RESULTS / "shots"                            # PNG-скриншоты labN_KK для вставки в отчёт
SUBMISSION_DIR = RESULTS / "submission"              # итоговые файлы для сдачи (vm/make_submission.py)

PROJECT_YAML = PACKAGE_ROOT / "project.yaml"
SIW_YAML = PACKAGE_ROOT / "siw" / "siw.yaml"          # СРС (SIW): источник build_siw.py
GUIDELINES_MD = PACKAGE_ROOT / "docs" / "guidelines" / "methodical-guidelines.md"
GUIDELINES_DOCX = "methodical-guidelines.docx"        # build_guidelines.py → out/
ARTIFACTS_MD = PACKAGE_ROOT / "docs" / "artifacts" / "example-conference-2026.md"
ARTIFACTS_DOCX = "project-artifacts.docx"             # build_artifacts.py → out/
SIW_REPORT_DOCX = "siw-report.docx"                   # build_siw.py → out/
SIW_REPORT_MD = "siw-report.md"                       # build_siw.py → out/
SIW_REPORT_READY_DOCX = "siw-report-final.docx"       # после вставки снимков (automation/fill_report.py)

# ---------- артефакты в out/ (build.py) ----------

XML_PLAN = "01_plan_lab1-2.xml"
XML_FULL = "02_full_lab3-7_9.xml"
XML_FULL_SAFE = "02_full_safe.xml"
XML_PERT_IN = "03_pert_input_lab8.xml"
XML_PERT_OUT = "04_pert_result_lab8.xml"
XML_VARIANTS = [XML_PLAN, XML_FULL, XML_FULL_SAFE, XML_PERT_IN, XML_PERT_OUT]

# XML дополнительного задания (практическая работа, варианты 12/10) — генерирует
# build_infosec.py; документация по варианту лежит в additional-assignment/<variant>/.
XML_INFOSEC_V12 = "infosec_v12_full.xml"
XML_INFOSEC_V10 = "infosec_v10_full.xml"
XML_INFOSEC_VARIANTS = [XML_INFOSEC_V12, XML_INFOSEC_V10]
XML_VARIANTS = XML_VARIANTS + XML_INFOSEC_VARIANTS

# .mpp — проприетарный бинарь MS Project; создаётся scripts/xml_to_mpp.py из XML
# через COM-автоматизацию (нужен установленный MS Project). Закоммичены для удобства:
# студент открывает .mpp напрямую, без ручного импорта XML.
MPP_VARIANTS = [name.replace(".xml", ".mpp") for name in XML_VARIANTS]

EXPECTED_JSON = "expected.json"
ANALYSIS_MD = "analysis.md"
REPORT_DOCX = "ms-project-labs-report.docx"              # заготовка из report.docx (build.py)
REPORT_READY_DOCX = "ms-project-labs-report-final.docx"  # после вставки скриншотов (automation/fill_report.py)

# .mpp, который пересобирает automation/ms_project_ui.py (lab9_02 → lab9_03): в нём
# добавлены настраиваемые поля «Общая стоимость» / «% от общей стоимости». Лежит в
# RESULTS (не в out/): это runtime-артефакт, а не канонический MANIFEST.
MPP_LAB9_COSTS = "09_costs_lab9.mpp"

# ---------- СРС (SIW) и сдача ----------

# ID мест под скриншоты СРС. Совпадают с siw/siw.yaml (поле shots) и с именами
# файлов automation/results/shots/siw_lrN_KK.png, которые снимает ВМ-агент.
SIW_SHOT_IDS = [
    "siw_lr1_01", "siw_lr1_02",
    "siw_lr2_01", "siw_lr2_02",
    "siw_lr3_01", "siw_lr3_02",
    "siw_lr4_01", "siw_lr4_02",
    "siw_lr5_01",
    "siw_lr6_01",
    "siw_lr7_01",
    "siw_lr8_01", "siw_lr8_02",
    "siw_lr9_01", "siw_lr9_02",
]

# (рабочий файл в out/, итоговое имя в submission/, ЛР, что внутри)
SUBMISSION_FILES = [
    (XML_PLAN, "01_lab1-2_plan", "ЛР1–2", "календарь, задачи, связи, вехи, ограничение, крайний срок"),
    (XML_FULL, "02_lab3-7-9_full", "ЛР3–7, 9", "ресурсы, стоимость, перегрузки, СДР, коды, критический путь"),
    (XML_FULL_SAFE, "03_lab3-7-9_safe", "ЛР3–7, 9", "запасной вариант без настраиваемых полей"),
    (XML_PERT_IN, "04_lab8_pert-input", "ЛР8", "три оценки PERT"),
    (XML_PERT_OUT, "05_lab8_pert-result", "ЛР8", "план по ожидаемым длительностям 1-4-1"),
    (XML_INFOSEC_V12, "06_assignment-12-pam", "ДЗ 12", "PAM: план внедрения и смета"),
    (XML_INFOSEC_V10, "07_assignment-10-dlp-siem", "ДЗ 10", "DLP + SIEM: план внедрения и смета"),
]
SUBMISSION_REPORT = "00_labs-report-with-screenshots.docx"
SUBMISSION_SIW = "00_siw-report.docx"

# ---------- манифест: исчерпывающий перечень канонических файлов ----------

MANIFEST: list[tuple[Path, str]] = [
    # build.py → out/
    (OUT, XML_PLAN), (OUT, XML_FULL), (OUT, XML_FULL_SAFE), (OUT, XML_PERT_IN), (OUT, XML_PERT_OUT),
    (OUT, EXPECTED_JSON), (OUT, ANALYSIS_MD), (OUT, REPORT_DOCX),
    # build_infosec.py → out/ (дополнительное задание, варианты 12/10)
    (OUT, XML_INFOSEC_V12), (OUT, XML_INFOSEC_V10),
    # build_siw.py / build_guidelines.py / build_artifacts.py → out/
    (OUT, SIW_REPORT_DOCX), (OUT, SIW_REPORT_MD), (OUT, GUIDELINES_DOCX), (OUT, ARTIFACTS_DOCX),
]
