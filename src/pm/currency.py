"""Валюты сметы: онлайн-курсы НБКР (основной источник) и ЦБ РФ (фоллбэк).

Смета СЗИ-проекта ведётся в базовой валюте project.yaml (`project.currency_code`,
для вариантов 10/12 — KGS), а импортные позиции (лицензии иностранных вендоров,
серверы) задаются в USD и переводятся по формуле

    сумма_баз = сумма_USD × курс_USD→баз     (для KGS: сумма × usd)

Курсы лежат в project.yaml в блоке `fx` — их подставляет scripts/fx_rate.py после
онлайн-запроса к НБКР, чтобы расчёт был воспроизводимым и не зависел от сети
ни при сборке, ни при проверке работы на машине без интернета.

Порядок источников: НБКР (`nbkr.kg/XML/daily.xml`, единственный легитимный
источник курса сома) → ЦБ РФ (`cbr.ru/scripts/XML_daily.asp`, есть и USD, и
KGS, но курс KGS там кросс-курс и расходится с НБКР примерно на 0,5 %) →
резервный FALLBACK с пометкой, чтобы молча не считать по устаревшему курсу.
"""
from __future__ import annotations

import datetime as dt
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .model import Project

NBKR_DAILY = "https://www.nbkr.kg/XML/daily.xml"
CBR_DAILY = "https://www.cbr.ru/scripts/XML_daily.asp"
# Резерв — последний онлайн-замер (см. отчёт: 14.10.2026, НБКР). Используется
# только скриптом при полной недоступности сети и всегда печатается с пометкой.
FALLBACK_USD = 87.45
FALLBACK_RUB = 1.0372
FALLBACK_DATE = dt.date(2026, 10, 14)
# Сколько дней считать кэш курса свежим: курс НБКР меняется раз в сутки
# (ставится ~16:00 по Бишкеку и действует со следующего дня).
CACHE_TTL_DAYS = 1
USER_AGENT = "Mozilla/5.0 (project-management fx)"


@dataclass(frozen=True)
class Fx:
    """Курсы базовой валюты проекта к USD и RUB на дату `date`.

    `usd` — сколько единиц базовой валюты за 1 USD, `rub` — за 1 RUB;
    для базы KGS это ровно то, что публикует НБКР.
    """

    date: dt.date
    source: str          # nbkr | cbr | fallback
    usd: float
    rub: float

    def factor(self, currency: str, base: str) -> float:
        """Множитель пересчёта из `currency` в `base` (1 → 1 для совпадения).

        Курсы в блоке fx всегда «базовая валюта за единицу валюты» (usd = сколько
        базы за 1 USD), поэтому множитель — отношение двух таких величин.
        """
        unit = {base: 1.0, "USD": self.usd, "RUB": self.rub}
        if currency not in unit or base not in unit:
            raise KeyError(f"Неизвестная валюта: {currency} → {base}")
        return unit[currency] / unit[base]


def _get(url: str) -> bytes:
    """Скачать URL одним запросом; таймаут 20 с — оба источника отвечают быстро."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def _num(text: str | None) -> float:
    # Оба источника отдают дробную часть через запятую (windows-1251, ru-локаль).
    return float((text or "0").replace(",", ".").strip())


def fetch_nbkr() -> Fx | None:
    """Курсы НБКР (USD и RUB к сому) на опубликованную дату; None при ошибке.

    Источник отдаёт всегда последнюю опубликованную дату (параметр ?date=
    игнорируется), поэтому дата берётся из атрибута Date самого XML.
    """
    try:
        root = ET.fromstring(_get(NBKR_DAILY))
    except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError):
        return None
    rates: dict[str, float] = {}
    for cur in root.findall("Currency"):
        iso = cur.get("ISOCode")
        if iso in ("USD", "RUB"):
            nominal = _num(cur.findtext("Nominal")) or 1.0
            rates[iso] = _num(cur.findtext("Value")) / nominal
    if not {"USD", "RUB"} <= rates.keys():
        return None
    try:
        date = dt.datetime.strptime(root.get("Date") or "", "%d.%m.%Y").date()
    except ValueError:
        date = dt.date.today()
    return Fx(date, "nbkr", rates["USD"], rates["RUB"])


def fetch_cbr() -> Fx | None:
    """Курсы ЦБ РФ → курс к сому; None при ошибке.

    ЦБ публикует RUB за 1 USD и RUB за 100 KGS, поэтому к сому обе величины
    считаются здесь: руб_за_сом = 1 / VunitRate(KGS), долл_за_сом =
    (RUB за USD) / (RUB за KGS).
    """
    try:
        root = ET.fromstring(_get(CBR_DAILY))
    except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError):
        return None
    unit: dict[str, float] = {}
    for val in root.findall("Valute"):
        code = val.findtext("CharCode")
        if code in ("USD", "KGS"):
            vr = val.findtext("VunitRate")
            if vr:
                unit[code] = _num(vr)
            else:
                unit[code] = _num(val.findtext("Value")) / int(val.findtext("Nominal") or 1)
    if not {"USD", "KGS"} <= unit.keys() or not unit["KGS"]:
        return None
    try:
        date = dt.datetime.strptime(root.get("Date") or "", "%d/%m/%Y").date()
    except ValueError:
        date = dt.date.today()
    return Fx(date, "cbr", unit["USD"] / unit["KGS"], 1.0 / unit["KGS"])


def fetch() -> Fx:
    """Онлайн-курс: НБКР → ЦБ РФ → резерв (с пометкой source='fallback')."""
    return fetch_nbkr() or fetch_cbr() or Fx(FALLBACK_DATE, "fallback", FALLBACK_USD, FALLBACK_RUB)


def from_yaml(data: dict) -> Fx | None:
    """Блок `fx` из project.yaml → Fx; без блока — None (конвертация не нужна)."""
    fx = data.get("fx")
    if not fx:
        return None
    date = fx.get("date")
    if isinstance(date, str):
        date = dt.date.fromisoformat(date)
    return Fx(date, str(fx.get("source", "yaml")), float(fx["usd"]), float(fx["rub"]))


def apply_fx(project: Project, fx: Fx) -> None:
    """Перевести цены валютных ресурсов в базовую валюту проекта (in place).

    Материальные ресурсы: конвертируется только цена за единицу — количество
    в назначении задачи остаётся штуками. Затратные: конвертируется сумма
    назначения (`task.res`). Трудовые: ставки, если часовой специалист указан
    в чужой валюте. Исходная цена сохраняется в `rate_src`, чтобы отчёт мог
    показать и USD, и KGS; повторный вызов отсекается по `rate_src`.
    """
    base = project.meta.get("currency_code") or "RUB"
    if project.meta.get("fx_applied"):
        return                      # повторный вызов не должен сконвертировать дважды
    for r in project.resources:
        cur = r.currency or base
        if cur == base or r.type == "cost" or r.rate_src is not None:
            continue                # у затратного ресурса ставок нет — конвертируются назначения
        k = fx.factor(cur, base)
        r.rate_src = r.rate
        r.rate = round(r.rate * k, 2)
        r.ot = round(r.ot * k, 2)
        if r.rate_b is not None:
            r.rate_b = round(r.rate_b * k, 2)
        r.per_use = round(r.per_use * k, 2)
        if r.rate_change:
            r.rate_change = {**r.rate_change, "rate": round(r.rate_change["rate"] * k, 2)}
    # Суммы затратных ресурсов живут в назначениях задач: конвертируем их отдельно.
    for t in project.tasks:
        for rk, u in list(t.res.items()):
            r = project.resource(rk)
            cur = r.currency or base
            if r.type == "cost" and cur != base:
                t.res[rk] = round(u * fx.factor(cur, base), 2)
    project.meta["fx_applied"] = True


def original(amount_kgs: float, currency: str, fx: Fx, base: str) -> float:
    """Обратный пересчёт: сумма в базовой валюте → исходная валюта (для таблицы)."""
    return round(amount_kgs / fx.factor(currency, base), 2)
