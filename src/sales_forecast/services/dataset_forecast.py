from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from sales_forecast.forecasting.errors import ForecastingError, ValidationImpossibleError
from sales_forecast.forecasting.metrics import calculate_metrics
from sales_forecast.forecasting.preparation import SUPPORTED_TARGETS, prepare_daily_series, validation_days
from sales_forecast.forecasting.prophet_adapter import ProphetForecaster
from sales_forecast.forecasting.seasonal_naive import SeasonalNaiveForecaster
from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.repositories.forecasts import ForecastRepository


logger = logging.getLogger(__name__)
MAX_HORIZON_DAYS = 365


@dataclass(frozen=True)
class ForecastExecution:
    forecast_id: int
    result: dict[str, object]


class DatasetForecastService:
    def __init__(
        self, session_factory: sessionmaker[Session], datasets: DatasetRepository | None = None,
        forecasts: ForecastRepository | None = None, prophet: ProphetForecaster | None = None,
        seasonal_naive: SeasonalNaiveForecaster | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._datasets = datasets or DatasetRepository()
        self._forecasts = forecasts or ForecastRepository()
        self._prophet = prophet or ProphetForecaster()
        self._seasonal_naive = seasonal_naive or SeasonalNaiveForecaster()

    def forecast(self, dataset_id: int, target: str = "revenue", horizon_days: int = 30) -> ForecastExecution:
        if target not in SUPPORTED_TARGETS:
            raise ForecastingError(f"Unsupported target '{target}'. Use revenue or units_sold.")
        if not 1 <= horizon_days <= MAX_HORIZON_DAYS:
            raise ForecastingError(f"horizon_days must be between 1 and {MAX_HORIZON_DAYS}.")
        with self._session_factory() as session:
            self._datasets.get_by_id(session, dataset_id)
            records = self._datasets.get_sales_records(session, dataset_id)
        series = prepare_daily_series(records, target)
        validation_size = validation_days(len(series))
        train, validation = series.iloc[:-validation_size].copy(), series.iloc[-validation_size:].copy()
        if len(train) < 7:
            raise ValidationImpossibleError("At least seven training days are required for weekly Seasonal Naive validation.")

        comparison = self._compare_models(train, validation)
        selected_model, selection_metric = _select_model(comparison)
        model = self._prophet if selected_model == "prophet" else self._seasonal_naive
        points = model.forecast(series, horizon_days)
        result = {
            "dataset_id": dataset_id,
            "target": target,
            "history": {"date_from": series.iloc[0].date.date().isoformat(), "date_to": series.iloc[-1].date.date().isoformat(), "number_of_days": len(series)},
            "validation": {"date_from": validation.iloc[0].date.date().isoformat(), "date_to": validation.iloc[-1].date.date().isoformat(), "days": validation_size},
            "model_comparison": comparison,
            "selected_model": selected_model,
            "selection_metric": selection_metric,
            "horizon_days": horizon_days,
            "forecast_points": points,
        }
        metrics = {"validation": result["validation"], "model_comparison": comparison, "selected_model": selected_model, "selection_metric": selection_metric}
        with self._session_factory() as session:
            with session.begin():
                stored = self._forecasts.create(session, dataset_id=dataset_id, target=target, model_name=selected_model,
                    horizon_days=horizon_days, metrics_json=metrics, forecast_json=result)
                forecast_id = stored.id
        assert forecast_id is not None
        return ForecastExecution(forecast_id=forecast_id, result=result)

    def _compare_models(self, train, validation) -> dict[str, dict[str, float | int | None]]:
        actual = validation["value"].astype(float).tolist()
        output: dict[str, dict[str, float | int | None]] = {}
        for name, model in (("prophet", self._prophet), ("seasonal_naive", self._seasonal_naive)):
            predictions = model.forecast(train, len(validation))
            values = [float(point["predicted"]) for point in predictions]
            output[name] = calculate_metrics(actual, values)
        return output


def _select_model(comparison: dict[str, dict[str, float | int | None]]) -> tuple[str, str]:
    prophet = comparison["prophet"]
    seasonal = comparison["seasonal_naive"]
    if prophet["mape"] is not None and seasonal["mape"] is not None:
        metric = "mape"
    else:
        metric = "mae"
    return ("prophet" if float(prophet[metric]) < float(seasonal[metric]) else "seasonal_naive", metric)
