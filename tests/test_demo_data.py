from datetime import date

from sales_forecast.services.csv_validation import read_and_validate_csv
from sales_forecast.services.demo_data import DEFAULT_DEMO_SEED, PRODUCTS, generate_demo_csv


def test_demo_generator_is_reproducible_and_valid(tmp_path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    assert generate_demo_csv(first_path, seed=DEFAULT_DEMO_SEED) == 365 * len(PRODUCTS)
    generate_demo_csv(second_path, seed=DEFAULT_DEMO_SEED)

    assert first_path.read_bytes() == second_path.read_bytes()
    records = read_and_validate_csv(first_path)
    assert len(records) == 365 * len(PRODUCTS)
    assert min(record.date for record in records) == date(2024, 1, 1)
