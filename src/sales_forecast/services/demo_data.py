"""Deterministic synthetic sales data for local demonstrations."""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DEFAULT_DEMO_SEED = 20260922
DEFAULT_DEMO_START = date(2024, 1, 1)
DEFAULT_DEMO_DAYS = 365
CSV_COLUMNS = (
    "date",
    "product",
    "category",
    "units_sold",
    "revenue",
    "price",
    "discount_pct",
    "ad_spend",
    "promo",
)

PRODUCTS = (
    ("Wireless Headphones", "Electronics", 72.0, 89.90, 0.82, 1.05),
    ("Smart Home Speaker", "Electronics", 48.0, 119.90, 0.72, 1.00),
    ("Organic Coffee", "Groceries", 125.0, 14.50, 0.35, 1.14),
    ("Trail Backpack", "Outdoor", 36.0, 74.90, 0.95, 0.92),
    ("Camping Lantern", "Outdoor", 42.0, 39.90, 0.76, 0.96),
)


def generate_demo_csv(
    output_path: Path,
    *,
    seed: int = DEFAULT_DEMO_SEED,
    start_date: date = DEFAULT_DEMO_START,
    days: int = DEFAULT_DEMO_DAYS,
) -> int:
    """Write a deterministic daily synthetic data set and return row count."""
    if days < 365:
        raise ValueError("days must be at least 365 for the demo dataset")

    randomizer = random.Random(seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_count = 0
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for day_index in range(days):
            current_date = start_date + timedelta(days=day_index)
            for product_index, product in enumerate(PRODUCTS):
                writer.writerow(_generate_row(randomizer, current_date, day_index, product_index, product))
                rows_count += 1
    return rows_count


def _generate_row(
    randomizer: random.Random,
    current_date: date,
    day_index: int,
    product_index: int,
    product: tuple[str, str, float, float, float, float],
) -> dict[str, str | int]:
    name, category, base_demand, base_price, price_sensitivity, weekend_factor = product
    week_position = current_date.weekday()
    yearly_position = 2 * math.pi * day_index / 365
    product_phase = product_index * 0.65
    long_trend = 1.0 + day_index * (0.00032 + product_index * 0.00002)
    weekly_seasonality = 1.0 + 0.10 * math.sin(2 * math.pi * week_position / 7 + product_phase)
    yearly_seasonality = 1.0 + 0.14 * math.sin(yearly_position + product_phase)
    weekend_effect = weekend_factor if week_position >= 5 else 1.0

    price_variation = 1.0 + randomizer.uniform(-0.08, 0.10) + 0.025 * math.sin(yearly_position * 3 + product_phase)
    list_price = base_price * price_variation
    discount_pct = 0.0
    if randomizer.random() < 0.24:
        discount_pct = randomizer.choice((5.0, 8.0, 10.0, 12.5, 15.0, 20.0))
    promo = randomizer.random() < (0.11 + (0.07 if discount_pct >= 10 else 0.0))
    ad_spend = max(0.0, 20 + base_demand * randomizer.uniform(0.65, 1.55) + 18 * math.sin(yearly_position + product_phase))

    price_effect = (base_price / list_price) ** price_sensitivity
    discount_uplift = 1.0 + 0.012 * discount_pct + 0.00035 * discount_pct**2
    advertising_effect = 1.0 + 0.28 * math.log1p(ad_spend) / math.log(1 + 180)
    promo_uplift = 1.18 if promo else 1.0
    noise = max(0.65, randomizer.gauss(1.0, 0.09))
    units_sold = max(
        0,
        round(
            base_demand
            * long_trend
            * weekly_seasonality
            * yearly_seasonality
            * weekend_effect
            * price_effect
            * discount_uplift
            * advertising_effect
            * promo_uplift
            * noise
        ),
    )

    effective_price = _money(list_price * (1 - discount_pct / 100))
    revenue = _money(units_sold * effective_price)
    return {
        "date": current_date.isoformat(),
        "product": name,
        "category": category,
        "units_sold": units_sold,
        "revenue": _format_decimal(revenue),
        "price": _format_decimal(_money(list_price)),
        "discount_pct": _format_decimal(Decimal(str(discount_pct)).quantize(Decimal("0.01"))),
        "ad_spend": _format_decimal(_money(ad_spend)),
        "promo": "true" if promo else "false",
    }


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_decimal(value: Decimal) -> str:
    return format(value, ".2f")
