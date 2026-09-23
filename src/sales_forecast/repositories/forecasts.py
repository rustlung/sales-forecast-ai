from __future__ import annotations

from sqlalchemy.orm import Session

from sales_forecast.database.models import Forecast


class ForecastRepository:
    def create(
        self, session: Session, *, dataset_id: int, target: str, model_name: str, horizon_days: int,
        metrics_json: dict[str, object], forecast_json: dict[str, object]
    ) -> Forecast:
        forecast = Forecast(
            dataset_id=dataset_id, target=target, model_name=model_name, horizon_days=horizon_days,
            metrics_json=metrics_json, forecast_json=forecast_json,
        )
        session.add(forecast)
        session.flush()
        return forecast
