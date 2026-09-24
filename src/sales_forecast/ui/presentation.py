"""Pure, Russian-language presentation helpers for the Streamlit dashboard."""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import pandas as pd


WEEKDAY_LABELS = {
    "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
    "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье",
}
MONTH_LABELS = {
    1: "янв.", 2: "фев.", 3: "мар.", 4: "апр.", 5: "мая", 6: "июн.",
    7: "июл.", 8: "авг.", 9: "сент.", 10: "окт.", 11: "нояб.", 12: "дек.",
}
MONTH_AXIS_LABELS = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек",
}
FEATURE_LABELS = {
    "price": "Цена", "discount_pct": "Скидка", "ad_spend": "Рекламные расходы",
    "weekday": "День недели", "month": "Месяц",
}


def format_decimal(value: object, digits: int = 2) -> str:
    """Format a finite number with Russian grouping and decimal separators."""
    if value is None or not _finite(value):
        return "—"
    return f"{float(value):,.{digits}f}".replace(",", " ").replace(".", ",")


def format_number(value: object, digits: int = 0) -> str:
    return format_decimal(value, digits)


def format_currency_like_value(value: object) -> str:
    """Format monetary-like data without inventing a currency symbol."""
    return format_decimal(value, 2)


def format_currency(value: object) -> str:
    """Backward-compatible name for monetary-like values."""
    return format_currency_like_value(value)


def format_percent(value: object, digits: int = 2) -> str:
    if value is None or not _finite(value):
        return "—"
    return f"{format_decimal(value, digits)}%"


def format_metric(value: object, metric: str) -> str:
    if metric == "r2":
        return format_decimal(value, 3)
    if metric == "mape":
        return format_percent(value)
    return format_decimal(value, 2)


def format_correlation(value: object) -> str:
    return format_decimal(value, 4)


def format_feature_importance(value: object) -> str:
    return format_decimal(value, 4)


def localize_weekday(value: object) -> str:
    return WEEKDAY_LABELS.get(str(value), str(value))


def localize_month(value: object) -> str:
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return MONTH_LABELS[value.month]
    try:
        return MONTH_LABELS[int(value)]
    except (KeyError, TypeError, ValueError):
        return str(value)


def russian_time_axis_ticks(values: Iterable[object], max_ticks: int = 8) -> tuple[list[pd.Timestamp], list[str]]:
    """Return sparse month ticks while retaining a real datetime axis."""
    dates = pd.to_datetime(list(values), errors="coerce")
    dates = dates[~dates.isna()]
    if len(dates) == 0:
        return [], []
    months = pd.Series(dates).dt.to_period("M").drop_duplicates().dt.to_timestamp().tolist()
    step = max(1, math.ceil(len(months) / max_ticks))
    selected = months[::step]
    if months[-1] not in selected:
        selected.append(months[-1])
    return selected, [f"{MONTH_AXIS_LABELS[item.month]} {item.year}" for item in selected]


def localize_feature_name(feature: object) -> str:
    """Convert sklearn ColumnTransformer names into human-readable Russian labels."""
    raw = str(feature)
    if raw.startswith("numeric__"):
        return FEATURE_LABELS.get(raw.removeprefix("numeric__"), raw)
    if raw.startswith("category__category_"):
        return f"Категория: {raw.removeprefix('category__category_')}"
    if raw.startswith("category__product_"):
        return f"Товар: {raw.removeprefix('category__product_')}"
    if raw.startswith("category__promo_"):
        value = raw.removeprefix("category__promo_").lower()
        return f"Промо: {'да' if value == 'true' else 'нет' if value == 'false' else value}"
    return raw


def forecast_dataframe(points: Iterable[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(points, columns=["date", "predicted", "lower", "upper"])
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("predicted", "lower", "upper"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[column] = frame[column].where(frame[column].map(lambda value: math.isfinite(value) if pd.notna(value) else False))
    return frame.dropna(subset=["date", "predicted"]).sort_values("date")


def optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
