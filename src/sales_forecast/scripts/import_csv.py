from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine, create_session_factory
from sales_forecast.logging_config import configure_logging
from sales_forecast.services.csv_validation import CsvValidationError
from sales_forecast.services.dataset_import import DatasetImportService


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and import a sales CSV into PostgreSQL.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--name", help="Dataset name; defaults to the CSV filename.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting CSV import from %s", args.csv_path)
    try:
        engine = create_engine(settings.database_url)
        service = DatasetImportService(create_session_factory(engine))
        result = service.import_csv(args.csv_path, args.name)
    except CsvValidationError as error:
        logger.error("CSV validation failed: %s", error)
        raise SystemExit(2) from None
    except FileNotFoundError:
        logger.error("CSV file was not found: %s", args.csv_path)
        raise SystemExit(2) from None

    logger.info("CSV import completed: dataset_id=%s rows_count=%s", result.dataset_id, result.rows_count)
    print(
        f"Imported dataset_id={result.dataset_id} rows_count={result.rows_count} "
        f"date_from={result.date_from} date_to={result.date_to}"
    )


if __name__ == "__main__":
    main()
