import json
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from sales_forecast.database.models import SalesRecord
from sales_forecast.forecasting.errors import InsufficientHistoryError, MissingDatesError
from sales_forecast.forecasting.metrics import calculate_metrics
from sales_forecast.forecasting.preparation import prepare_daily_series
from sales_forecast.forecasting.prophet_adapter import ProphetForecaster
from sales_forecast.forecasting.seasonal_naive import SeasonalNaiveForecaster
from sales_forecast.services.dataset_forecast import _select_model


def _records(days: int, *, skip_day: int | None = None) -> list[SalesRecord]:
    result = []
    for index in range(days):
        if index == skip_day:
            continue
        result.append(SalesRecord(dataset_id=1, date=date(2025, 1, 1) + timedelta(days=index), product="P", category="C",
            units_sold=index + 1, revenue=Decimal(index + 1), price=Decimal("1"), discount_pct=Decimal("0"), ad_spend=Decimal("0"), promo=False))
    return result


def test_daily_preparation_aggregates_and_rejects_missing_or_short_history() -> None:
    rows = _records(90)
    rows.append(SalesRecord(dataset_id=1, date=date(2025, 1, 1), product="P2", category="C", units_sold=1,
        revenue=Decimal("5"), price=Decimal("1"), discount_pct=Decimal("0"), ad_spend=Decimal("0"), promo=False))
    series = prepare_daily_series(list(reversed(rows)), "revenue")
    assert len(series) == 90 and series.iloc[0].value == 6.0 and series.date.is_monotonic_increasing
    with pytest.raises(InsufficientHistoryError):
        prepare_daily_series(_records(89), "revenue")
    with pytest.raises(MissingDatesError):
        prepare_daily_series(_records(90, skip_day=20), "revenue")


def test_seasonal_naive_repeats_weekly_pattern_deterministically() -> None:
    history = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=14), "value": list(range(1, 15))})
    model = SeasonalNaiveForecaster()
    seven = model.forecast(history, 7)
    ten = model.forecast(history, 10)
    assert [point["predicted"] for point in seven] == list(range(8, 15))
    assert [point["predicted"] for point in ten] == list(range(8, 15)) + [8, 9, 10]
    assert model.forecast(history, 10) == ten


def test_metrics_zero_actuals_and_selection_fallback_are_safe() -> None:
    metrics = calculate_metrics([0, 10], [5, 5])
    assert metrics == {"mae": 5.0, "rmse": 5.0, "mape": 50.0, "zero_actual_count": 1}
    zero_heavy = calculate_metrics([0, 0, 10], [1, 1, 8])
    assert zero_heavy["mape"] is None
    assert json.dumps(zero_heavy)
    winner, criterion = _select_model({"prophet": {"mae": 4.0, "mape": None}, "seasonal_naive": {"mae": 3.0, "mape": None}})
    assert (winner, criterion) == ("seasonal_naive", "mae")
    winner, criterion = _select_model({"prophet": {"mae": 4.0, "mape": 2.0}, "seasonal_naive": {"mae": 1.0, "mape": 3.0}})
    assert (winner, criterion) == ("prophet", "mape")


def test_prophet_adapter_uses_ds_y_and_clips_negative_output() -> None:
    captured = {}

    class FakeProphet:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
        def fit(self, frame):
            captured["columns"] = list(frame.columns)
        def make_future_dataframe(self, periods, freq, include_history):
            captured["future"] = (periods, freq, include_history)
            return pd.DataFrame({"ds": pd.date_range("2025-01-03", periods=periods)})
        def predict(self, frame):
            return pd.DataFrame({"ds": frame["ds"], "yhat": [-2.0] * len(frame), "yhat_lower": [-4.0] * len(frame), "yhat_upper": [3.0] * len(frame)})

    history = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=2), "value": [1.0, 2.0]})
    points = ProphetForecaster(FakeProphet).forecast(history, 2)

    assert captured["columns"] == ["ds", "y"]
    assert captured["future"] == (2, "D", False)
    assert points[0]["predicted"] == 0.0 and points[0]["lower"] == 0.0 and points[0]["upper"] == 3.0
