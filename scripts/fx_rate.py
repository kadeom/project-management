"""Печатает блок fx для project.yaml по онлайн-курсу (НБКР → ЦБ РФ → резерв).

Использование:
    py scripts/fx_rate.py [--budget 12000000]

Подставляет результат в project.yaml вручную (или через переадресацию вывода):
    py scripts/fx_rate.py >> additional-assignment/01-pam/project.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pm import currency  # noqa: E402

BUDGET_NOTE = (
    "# Курсы онлайн-замера ({date}, источник: {source}); сом — базовая валюта проекта, "
    "USD — импортные позиции.\n"
    "# {budget:,} ₽ × {rub} KGS/₽ = {kgs:,} KGS (бюджет проекта в сомах).\n"
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Блок fx для project.yaml по онлайн-курсу")
    ap.add_argument("--budget", type=float, default=12_000_000, help="бюджет в рублях")
    args = ap.parse_args()

    fx = currency.fetch()
    print(BUDGET_NOTE.format(
        date=fx.date.isoformat(), source=fx.source,
        budget=args.budget, rub=fx.rub, kgs=round(args.budget * fx.rub, 2),
    ))
    print("fx:")
    print(f"  date: {fx.date.isoformat()}")
    print(f"  source: {fx.source}")
    print(f"  usd: {fx.usd}    # KGS за 1 USD")
    print(f"  rub: {fx.rub}  # KGS за 1 RUB")
    if fx.source == "fallback":
        print("# ВНИМАНИЕ: оба источника недоступны, курс — резервный!", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
