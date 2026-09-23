from __future__ import annotations

import argparse
import logging

from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine, create_session_factory
from sales_forecast.forecasting.errors import ForecastingError
from sales_forecast.logging_config import configure_logging
from sales_forecast.repositories.datasets import DatasetNotFoundError
from sales_forecast.services.dataset_forecast import DatasetForecastService


def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast daily sales target for an imported dataset.")
    parser.add_argument("dataset_id", type=int)
    parser.add_argument("--target", default="revenue", choices=("revenue", "units_sold"))
    parser.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    try:
        service = DatasetForecastService(create_session_factory(create_engine(get_settings().database_url)))
        execution = service.forecast(args.dataset_id, args.target, args.horizon)
    except (DatasetNotFoundError, ForecastingError) as error:
        logging.getLogger(__name__).error("Forecast failed: %s", error)
        raise SystemExit(2) from None
    result = execution.result
    comparison = result["model_comparison"]
    points = result["forecast_points"]
    print(
        f"forecast_id={execution.forecast_id} dataset_id={args.dataset_id} target={args.target} "
        f"selected_model={result['selected_model']} horizon={args.horizon} "
        f"prophet_mape={comparison['prophet']['mape']} seasonal_naive_mape={comparison['seasonal_naive']['mape']} "
        f"first_forecast_date={points[0]['date']} last_forecast_date={points[-1]['date']}"
    )


if __name__ == "__main__":
    main()
