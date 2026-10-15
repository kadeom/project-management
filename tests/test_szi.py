"""Практическая работа (ДЗ): блоки, скриншоты, Markdown и DOCX для вариантов 10/12.

Запуск: py -m pytest tests -q
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pm import model, report_szi  # noqa: E402

VARIANTS = [
    ("additional-assignment/01-pam/project.yaml", "v12"),
    ("additional-assignment/02-dlp-siem/project.yaml", "v10"),
]


@pytest.fixture
def workdir():
    """Каталог для временных .docx (штатный tmp_path в этой среде недоступен)."""
    d = Path(tempfile.mkdtemp(prefix="szi-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.parametrize("yaml_path,prefix", VARIANTS)
def test_blocks_render(yaml_path, prefix):
    project = model.load(yaml_path)
    data = report_szi.load_yaml(yaml_path)
    B = report_szi.blocks(project, data, prefix)
    assert B and all(isinstance(b, tuple) and b[0] for b in B)
    heads = [b[1] for b in B if b[0] == "h1"]
    assert heads[0].startswith("1.") and heads[-1].startswith("11.")
    assert any(h.startswith("9.") for h in heads)
    text = report_szi.markdown(B)
    assert "9. Расчётная часть" in text and "Крайние сроки вех" in text
    assert " сом" in text and "None" not in text


@pytest.mark.parametrize("yaml_path,prefix", VARIANTS)
def test_shot_ids(yaml_path, prefix):
    project = model.load(yaml_path)
    data = report_szi.load_yaml(yaml_path)
    ids = [b[2] for b in report_szi.blocks(project, data, prefix) if b[0] == "shot"]
    assert ids == report_szi.shot_ids(prefix)
    assert len(set(ids)) == 5


def test_shot_ids_all_prefixes():
    assert report_szi.shot_ids("v12") == [f"v12_{i:02d}" for i in range(1, 6)]
    assert report_szi.shot_ids("v10") == [f"v10_{i:02d}" for i in range(1, 6)]


@pytest.mark.parametrize("yaml_path,prefix", VARIANTS)
def test_docx_writes(yaml_path, prefix, workdir):
    project = model.load(yaml_path)
    data = report_szi.load_yaml(yaml_path)
    out = report_szi.docx(project, data, workdir / f"{prefix}.docx", prefix)
    assert out.exists() and out.stat().st_size > 10_000


def test_deadline_reserve_nonnegative(yaml_path="additional-assignment/01-pam/project.yaml"):
    project = model.load(yaml_path)
    text = report_szi.markdown(report_szi.blocks(project, report_szi.load_yaml(yaml_path), "v12"))
    line = next(x for x in text.splitlines() if x.startswith("Крайние сроки вех"))
    reserves = [int(p) for part in line.split("запас ")[1:] for p in [part.split()[0]]]
    assert reserves and all(r >= 0 for r in reserves)
