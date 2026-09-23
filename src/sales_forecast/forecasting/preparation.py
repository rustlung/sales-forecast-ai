from __future__ import annotations

from datetime import date

import pandas as pd

from sales_forecast.database.models import SalesRecord
from sales_forecast.forecasting.errors import InsufficientHistoryError, MissingDatesError, UnsupportedTargetError


SUPPORTED_TARGETS = ("revenue", "units_sold")
MIN_HISTORY_DAYS = 90


def prepare_daily_series(records: list[SalesRecord], target: str) -> pd.DataFrame:
    if target not in SUPPORTED_TARGETS:
        raise UnsupportedTargetError(f"Unsupported target '{target}'. Use revenue or units_sold.")
    rows = [{"date": record.date, "value": getattr(record, target)} for record in records]
    if not rows:
        raise InsufficientHistoryError(f"Forecasting requires at least {MIN_HISTORY_DAYS} calendar days; dataset has no records.")
    series = pd.DataFrame(rows)
    series["date"] = pd.to_datetime(series["date"])
    series["value"] = pd.to_numeric(series["value"], errors="raise").astype(float)
    series = series.groupby("date", as_index=False)["value"].sum().sort_values("date").reset_index(drop=True)
    expected_dates = pd.date_range(series["date"].min(), series["date"].max(), freq="D")
    missing_dates = expected_dates.difference(series["date"])
    if len(missing_dates):
        preview = ", ".join(day.date().isoformat() for day in missing_dates[:3])
        raise MissingDatesError(f"Daily series has {len(missing_dates)} missing calendar date(s), starting with {preview}. Import explicit zero-sales days if they are valid for this dataset.")
    if len(series) < MIN_HISTORY_DAYS:
        raise InsufficientHistoryError(f"Forecasting requires at least {MIN_HISTORY_DAYS} calendar days; dataset has {len(series)}.")
    return series


def validation_days(number_of_days: int) -> int:
    days = min(30, max(14, number_of_days // 5))
    if number_of_days - days < 60:
        raise InsufficientHistoryError("Forecasting needs at least 60 training days after the validation tail.")
    return days
