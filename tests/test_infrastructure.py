from sqlalchemy import text
from sales_forecast.database.session import create_engine
from sales_forecast.logging_config import configure_logging


def test_engine_factory_and_logging_smoke() -> None:
    configure_logging("INFO")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    engine.dispose()
