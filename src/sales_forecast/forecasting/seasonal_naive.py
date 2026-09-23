from __future__ import annotations

from datetime import timedelta


class SeasonalNaiveForecaster:
    """Weekly seasonal baseline for daily data, without confidence intervals."""

    seasonal_lag_days = 7

    def forecast(self, history: pd.DataFrame, horizon_days: int) -> list[dict[str, object]]:
        values = history["value"].astype(float).tolist()
        dates = history["date"].tolist()
        output: list[dict[str, object]] = []
        for _ in range(horizon_days):
            predicted = max(0.0, values[-self.seasonal_lag_days])
            next_date = dates[-1] + timedelta(days=1)
            values.append(predicted)
            dates.append(next_date)
            output.append({"date": next_date.date().isoformat(), "predicted": predicted, "lower": None, "upper": None})
        return output
