"""Курсы валют: формулы пересчёта, разбор ответов НБКР/ЦБ РФ, блок fx в модели.

Запуск: py -m pytest tests -q
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from pm import currency, model  # noqa: E402

FX = currency.Fx(dt.date(2026, 10, 15), "nbkr", usd=87.45, rub=1.0372)


@pytest.fixture
def workdir():
    """Каталог для временных project.yaml (штатный tmp_path в этой среде недоступен)."""
    d = Path(tempfile.mkdtemp(prefix="fx-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)

NBKR_XML = b"""<?xml version="1.0" encoding="windows-1251"?>
<DailyExRates Date="15.10.2026">
  <Currency ISO="R" ISOCode="RUB" Nominal="1"><Name>\xe2\xe0\xeb\xff\xfa\xe0</Name><Value>1,0438</Value></Currency>
  <Currency ISO="U" ISOCode="USD" Nominal="1"><Name>\xe4\xee\xeb\xeb\xe0\xf0 \xe1\xdd\xea\xe0\xfe\xe0\xeb\xfc\xed\xfb\xe5 \x8b\xed\xe2\xfb\xe2\xe0\xed\xe8\xe5</Name><Value>87,4500</Value></Currency>
</DailyExRates>
"""

CBR_XML = b"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="14/10/2026">
  <Valute ID="R01235"><Nominal>1</Nominal><CharCode>USD</CharCode><Name>\x24</Name><Value>83,9153</Value><VunitRate>83,915300</VunitRate></Valute>
  <Valute ID="R01200"><Nominal>100</Nominal><CharCode>KGS</CharCode><Name>Kyrgyz som</Name><Value>95,9580</Value><VunitRate>0,959580</VunitRate></Valute>
</ValCurs>
"""


# ---------- формулы ----------

def test_factor_converts_base_usd_rub():
    assert FX.factor("USD", "KGS") == 87.45
    assert FX.factor("RUB", "KGS") == 1.0372
    assert FX.factor("KGS", "KGS") == 1.0


def test_factor_unknown_currency_raises():
    with pytest.raises(KeyError):
        FX.factor("EUR", "KGS")


def test_original_roundtrips():
    kgs = 35000 * FX.factor("USD", "KGS")
    assert currency.original(kgs, "USD", FX, "KGS") == 35000.0


# ---------- разбор источников ----------

def test_fetch_nbkr_parses_xml(monkeypatch):
    monkeypatch.setattr(currency, "_get", lambda url: NBKR_XML)
    fx = currency.fetch_nbkr()
    assert fx == currency.Fx(dt.date(2026, 10, 15), "nbkr", 87.45, 1.0438)


def test_fetch_cbr_crosses_to_kgs(monkeypatch):
    monkeypatch.setattr(currency, "_get", lambda url: CBR_XML)
    fx = currency.fetch_cbr()
    assert fx.source == "cbr"
    assert fx.usd == pytest.approx(83.9153 / 0.95958, rel=1e-9)
    assert fx.rub == pytest.approx(1 / 0.95958, rel=1e-9)


def test_fetch_falls_back_when_sources_down(monkeypatch):
    monkeypatch.setattr(currency, "_get", lambda url: (_ for _ in ()).throw(OSError("offline")))
    fx = currency.fetch()
    assert fx.source == "fallback"
    assert fx.usd == currency.FALLBACK_USD


def test_fetch_prefers_nbkr_over_cbr(monkeypatch):
    monkeypatch.setattr(currency, "fetch_nbkr", lambda: FX)
    monkeypatch.setattr(currency, "fetch_cbr", lambda: None)
    assert currency.fetch() is FX


# ---------- блок fx в YAML ----------

def test_from_yaml_reads_block():
    fx = currency.from_yaml({"fx": {"date": "2026-10-15", "source": "nbkr",
                                    "usd": 87.45, "rub": 1.0372}})
    assert fx.date == dt.date(2026, 10, 15) and fx.usd == 87.45
    assert currency.from_yaml({}) is None


MINI_YAML = """
project: {name: Тест, start: 2026-10-05, currency: сом, currency_code: KGS, budget_rub: 12000000}
fx: {date: 2026-10-15, source: nbkr, usd: 87.45, rub: 1.0372}
calendar: {work_hours: [["08:00", "12:00"], ["13:00", "17:00"]]}
resources:
  - {key: SERV, name: Серверы, type: material, rate: 1000, currency: USD, label: шт.}
  - {key: BUY, name: Закупка, type: cost, currency: USD}
  - {key: PM, name: Руководитель, type: work, rate: 1100, role: Управление проектом}
phases:
  - name: Планирование
    tasks:
      - {key: t1, name: Закупка, dur: 5, pert: [4, 5, 6], res: {SERV: 2, BUY: 5000, PM: 0.5}}
"""


def test_load_converts_usd_to_base(workdir):
    f = workdir / "project.yaml"
    f.write_text(MINI_YAML, encoding="utf-8")
    p = model.load(f)
    assert p.resource("SERV").rate == pytest.approx(1000 * 87.45)   # цена → сом
    assert p.resource("SERV").rate_src == 1000                       # исходный USD сохранён
    assert p.task("t1").res["SERV"] == 2                             # количество осталось штуками
    assert p.task("t1").res["BUY"] == pytest.approx(5000 * 87.45)    # сумма затратного → сом
    assert p.resource("PM").rate == 1100 and p.resource("PM").rate_src is None


def test_apply_fx_is_idempotent(workdir):
    f = workdir / "project.yaml"
    f.write_text(MINI_YAML, encoding="utf-8")
    p = model.load(f)
    first = p.resource("SERV").rate
    currency.apply_fx(p, FX)                       # повторный вызов не должен конвертировать снова
    assert p.resource("SERV").rate == first
    assert p.task("t1").res["BUY"] == pytest.approx(5000 * 87.45)


def test_no_fx_block_keeps_values(workdir):
    f = workdir / "project.yaml"
    f.write_text(MINI_YAML.replace("fx: {date: 2026-10-15, source: nbkr, usd: 87.45, rub: 1.0372}\n", ""),
                 encoding="utf-8")
    p = model.load(f)
    assert p.resource("SERV").rate == 1000
    assert p.task("t1").res["BUY"] == 5000
