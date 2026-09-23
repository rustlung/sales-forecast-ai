from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from prophet import Prophet

from sales_forecast.forecasting.errors import ProphetTrainingError


class ProphetForecaster:
    def __init__(self, factory: Callable[..., Prophet] = Prophet) -> None:
        self._factory = factory

    def forecast(self, history: pd.DataFrame, horizon_days: int) -> list[dict[str, object]]:
        frame = history.rename(columns={"date": "ds", "value": "y"})[["ds", "y"]].copy()
        try:
            model = self._factory(
                weekly_seasonality=True,
                yearly_seasonality=len(frame) >= 730,
                daily_seasonality=False,
            )
            model.fit(frame)
            prediction = model.predict(model.make_future_dataframe(periods=horizon_days, freq="D", include_history=False))
        except Exception as error:
            raise ProphetTrainingError("Prophet could not train on this daily series.") from error
        return [
            {
                "date": row.ds.date().isoformat(),
                "predicted": max(0.0, _number(row.yhat)),
                "lower": max(0.0, _number(row.yhat_lower)),
                "upper": max(0.0, _number(row.yhat_upper)),
            }
            for row in prediction.itertuples(index=False)
        ]


def _number(value: object) -> float:
    return float(value)
