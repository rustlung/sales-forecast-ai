from __future__ import annotations

import logging

from sqlalchemy import text

from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine
from sales_forecast.logging_config import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Configuration loaded; testing PostgreSQL connectivity")
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()
    logger.info("PostgreSQL connectivity check passed")


if __name__ == "__main__":
    main()
