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

PROJECT_YAML = PACKAGE_ROOT / "project.yaml"

# ---------- артефакты в out/ (build.py) ----------

XML_PLAN = "01_plan_LR1-2.xml"
XML_FULL = "02_full_LR3-7_9.xml"
XML_FULL_SAFE = "02_full_safe.xml"
XML_PERT_IN = "03_pert_input_LR8.xml"
XML_PERT_OUT = "04_pert_result_LR8.xml"
XML_VARIANTS = [XML_PLAN, XML_FULL, XML_FULL_SAFE, XML_PERT_IN, XML_PERT_OUT]

EXPECTED_JSON = "expected.json"
ANALYSIS_MD = "analysis.md"
REPORT_DOCX = "Отчёт_ЛР_MS_Project.docx"              # заготовка из report.docx (build.py)

# ---------- манифест: исчерпывающий перечень канонических файлов ----------

MANIFEST: list[tuple[Path, str]] = [
    # build.py → out/
    (OUT, XML_PLAN), (OUT, XML_FULL), (OUT, XML_FULL_SAFE), (OUT, XML_PERT_IN), (OUT, XML_PERT_OUT),
    (OUT, EXPECTED_JSON), (OUT, ANALYSIS_MD), (OUT, REPORT_DOCX),
]
