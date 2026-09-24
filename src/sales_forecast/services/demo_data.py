"""Deterministic synthetic sales data for local demonstrations."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DEFAULT_DEMO_SEED = 20260922
RU_DEMO_SEED = 20260924
MANUAL_ACCEPTANCE_RU_SEED = 20260925
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

RU_PRODUCTS = (
    ("Робот-пылесос", "Электроника", 19.0, 26990.0, 1.14, 1.12),
    ("Электрический чайник", "Кухня", 44.0, 3490.0, 0.78, 1.09),
    ("Кофеварка", "Кухня", 24.0, 8990.0, 1.02, 0.97),
    ("Увлажнитель воздуха", "Дом и быт", 32.0, 5790.0, 0.88, 1.18),
    ("Набор посуды", "Дом и быт", 28.0, 6490.0, 0.65, 1.15),
    ("Фен", "Красота", 38.0, 4290.0, 0.91, 1.05),
)

MANUAL_ACCEPTANCE_RU_PRODUCTS = (
    ("Беговая дорожка", "Фитнес", 11.0, 48990.0, 1.20, 1.04),
    ("Гантели разборные", "Фитнес", 52.0, 6990.0, 0.62, 1.08),
    ("Палатка туристическая", "Туризм", 18.0, 15990.0, 1.05, 1.28),
    ("Спальный мешок", "Туризм", 31.0, 7490.0, 0.84, 1.16),
    ("Велосипед городской", "Велоспорт", 14.0, 32990.0, 1.16, 1.14),
    ("Лыжный комплект", "Зимний спорт", 12.0, 21990.0, 1.10, 0.92),
)


@dataclass(frozen=True)
class DemoProfile:
    products: tuple[tuple[str, str, float, float, float, float], ...]
    seed: int
    trend_base: float
    trend_product_step: float
    weekly_amplitude: float
    yearly_amplitude: float
    discount_probability: float
    promo_probability: float
    promo_discount_bonus: float
    ad_base: float
    ad_demand_low: float
    ad_demand_high: float
    ad_seasonal_amplitude: float
    advertising_coefficient: float
    advertising_saturation: float
    promo_uplift: float
    noise_floor: float
    noise_sigma: float
    start_date: date = DEFAULT_DEMO_START
    days: int = DEFAULT_DEMO_DAYS


DEFAULT_PROFILE = DemoProfile(
    PRODUCTS, DEFAULT_DEMO_SEED, 0.00032, 0.00002, 0.10, 0.14, 0.24, 0.11, 0.07,
    20, 0.65, 1.55, 18, 0.28, 180, 1.18, 0.65, 0.09,
)
RU_PROFILE = DemoProfile(
    RU_PRODUCTS, RU_DEMO_SEED, 0.00022, 0.000035, 0.13, 0.19, 0.30, 0.10, 0.10,
    90, 0.85, 2.10, 42, 0.38, 420, 1.23, 0.58, 0.12,
)
MANUAL_ACCEPTANCE_RU_PROFILE = DemoProfile(
    MANUAL_ACCEPTANCE_RU_PRODUCTS, MANUAL_ACCEPTANCE_RU_SEED, 0.00016, 0.00005, 0.16, 0.24, 0.27, 0.08, 0.12,
    130, 0.75, 2.45, 65, 0.42, 600, 1.26, 0.55, 0.14, date(2023, 3, 1), 455,
)
DEMO_PROFILES = {"default": DEFAULT_PROFILE, "ru": RU_PROFILE, "manual-acceptance-ru": MANUAL_ACCEPTANCE_RU_PROFILE}


def generate_demo_csv(
    output_path: Path,
    *,
    seed: int | None = None,
    start_date: date | None = None,
    days: int | None = None,
    profile: str = "default",
) -> int:
    """Write a deterministic daily synthetic data set and return row count."""
    try:
        selected_profile = DEMO_PROFILES[profile]
    except KeyError as error:
        raise ValueError(f"Unknown demo profile '{profile}'. Use one of: {', '.join(DEMO_PROFILES)}") from error
    selected_start_date = start_date or selected_profile.start_date
    selected_days = days if days is not None else selected_profile.days
    if selected_days < 365:
        raise ValueError("days must be at least 365 for the demo dataset")
    randomizer = random.Random(selected_profile.seed if seed is None else seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_count = 0
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for day_index in range(selected_days):
            current_date = selected_start_date + timedelta(days=day_index)
            for product_index, product in enumerate(selected_profile.products):
                writer.writerow(_generate_row(randomizer, current_date, day_index, product_index, product, selected_profile))
                rows_count += 1
    return rows_count


def _generate_row(
    randomizer: random.Random,
    current_date: date,
    day_index: int,
    product_index: int,
    product: tuple[str, str, float, float, float, float],
    profile: DemoProfile,
) -> dict[str, str | int]:
    name, category, base_demand, base_price, price_sensitivity, weekend_factor = product
    week_position = current_date.weekday()
    yearly_position = 2 * math.pi * day_index / 365
    product_phase = product_index * 0.65
    long_trend = 1.0 + day_index * (profile.trend_base + product_index * profile.trend_product_step)
    weekly_seasonality = 1.0 + profile.weekly_amplitude * math.sin(2 * math.pi * week_position / 7 + product_phase)
    yearly_seasonality = 1.0 + profile.yearly_amplitude * math.sin(yearly_position + product_phase)
    weekend_effect = weekend_factor if week_position >= 5 else 1.0

    price_variation = 1.0 + randomizer.uniform(-0.08, 0.10) + 0.025 * math.sin(yearly_position * 3 + product_phase)
    list_price = base_price * price_variation
    discount_pct = 0.0
    if randomizer.random() < profile.discount_probability:
        discount_pct = randomizer.choice((5.0, 8.0, 10.0, 12.5, 15.0, 20.0))
    promo = randomizer.random() < (profile.promo_probability + (profile.promo_discount_bonus if discount_pct >= 10 else 0.0))
    ad_spend = max(0.0, profile.ad_base + base_demand * randomizer.uniform(profile.ad_demand_low, profile.ad_demand_high) + profile.ad_seasonal_amplitude * math.sin(yearly_position + product_phase))

    price_effect = (base_price / list_price) ** price_sensitivity
    discount_uplift = 1.0 + 0.012 * discount_pct + 0.00035 * discount_pct**2
    advertising_effect = 1.0 + profile.advertising_coefficient * math.log1p(ad_spend) / math.log(1 + profile.advertising_saturation)
    promo_uplift = profile.promo_uplift if promo else 1.0
    noise = max(profile.noise_floor, randomizer.gauss(1.0, profile.noise_sigma))
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
