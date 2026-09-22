from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine, create_session_factory
from sales_forecast.logging_config import configure_logging
from sales_forecast.repositories.datasets import DatasetNotFoundError
from sales_forecast.services.dataset_analysis import DatasetAnalysisService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic descriptive analytics for a dataset.")
    parser.add_argument("dataset_id", type=int)
    parser.add_argument("--output-json", type=Path, help="Optional path for the complete analysis JSON.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting descriptive analysis for dataset_id=%s", args.dataset_id)
    try:
        service = DatasetAnalysisService(create_session_factory(create_engine(settings.database_url)))
        execution = service.analyze(args.dataset_id)
    except DatasetNotFoundError:
        logger.error("Dataset does not exist: dataset_id=%s", args.dataset_id)
        raise SystemExit(2) from None
    except Exception:
        logger.error("Analysis did not complete for dataset_id=%s", args.dataset_id)
        raise SystemExit(1) from None

    if args.output_json:
        args.output_json.write_text(json.dumps(execution.result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Full analysis JSON saved to %s", args.output_json)
    kpis = execution.result["kpis"]
    print(
        f"analysis_run_id={execution.analysis_run_id} total_revenue={kpis['total_revenue']:.2f} "
        f"units_sold={kpis['total_units_sold']} date_from={kpis['date_from']} date_to={kpis['date_to']} "
        f"products={kpis['number_of_products']} categories={kpis['number_of_categories']}"
    )


if __name__ == "__main__":
    main()
