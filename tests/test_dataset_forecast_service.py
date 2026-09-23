from contextlib import AbstractContextManager
from datetime import date, timedelta
from decimal import Decimal
import json

from sales_forecast.database.models import Dataset, Forecast, SalesRecord
from sales_forecast.services.dataset_forecast import DatasetForecastService


class _Tx(AbstractContextManager):
    def __enter__(self): return self
    def __exit__(self, *args): return False


class _Session(AbstractContextManager):
    def begin(self): return _Tx()
    def __exit__(self, *args): return False


class _Datasets:
    def __init__(self):
        self.dataset = Dataset(id=1, name="D", original_filename="d.csv", rows_count=100)
        self.records = [SalesRecord(dataset_id=1, date=date(2025, 1, 1) + timedelta(days=i), product="P", category="C", units_sold=i + 1,
            revenue=Decimal(i + 1), price=Decimal("1"), discount_pct=Decimal("0"), ad_spend=Decimal("0"), promo=False) for i in range(100)]
    def get_by_id(self, session, dataset_id): return self.dataset
    def get_sales_records(self, session, dataset_id): return self.records


class _Forecaster:
    def __init__(self, shift: float): self.shift = shift
    def forecast(self, history, horizon_days):
        return [{"date": (history.iloc[-1].date + timedelta(days=i + 1)).date().isoformat(), "predicted": float(history.iloc[-7 + (i % 7)].value) + self.shift, "lower": None, "upper": None} for i in range(horizon_days)]


class _Forecasts:
    def create(self, session, **kwargs):
        self.kwargs = kwargs
        return Forecast(id=55, **kwargs)


def test_successful_forecast_persists_selected_model_and_json() -> None:
    repository = _Forecasts()
    service = DatasetForecastService(lambda: _Session(), datasets=_Datasets(), forecasts=repository,
        prophet=_Forecaster(50), seasonal_naive=_Forecaster(0))
    execution = service.forecast(1, "revenue", 30)
    assert execution.forecast_id == 55
    assert repository.kwargs["dataset_id"] == 1 and repository.kwargs["target"] == "revenue"
    assert repository.kwargs["horizon_days"] == 30
    assert execution.result["selected_model"] == "seasonal_naive"
    assert len(execution.result["forecast_points"]) == 30
    json.dumps(repository.kwargs["forecast_json"])
