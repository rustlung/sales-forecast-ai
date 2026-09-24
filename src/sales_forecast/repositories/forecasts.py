from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select

from sales_forecast.database.models import Forecast


class ForecastRepository:
    def latest_for_target(self, session: Session, dataset_id: int, target: str) -> Forecast | None:
        statement = (
            select(Forecast)
            .where(Forecast.dataset_id == dataset_id, Forecast.target == target)
            .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        )
        return session.scalar(statement)

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
