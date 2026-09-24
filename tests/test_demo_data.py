from datetime import date

from sales_forecast.services.csv_validation import read_and_validate_csv
from sales_forecast.services.demo_data import (
    DEFAULT_DEMO_SEED, MANUAL_ACCEPTANCE_RU_PRODUCTS, MANUAL_ACCEPTANCE_RU_SEED,
    PRODUCTS, RU_DEMO_SEED, RU_PRODUCTS, generate_demo_csv,
)


def test_demo_generator_is_reproducible_and_valid(tmp_path) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    assert generate_demo_csv(first_path, seed=DEFAULT_DEMO_SEED) == 365 * len(PRODUCTS)
    generate_demo_csv(second_path, seed=DEFAULT_DEMO_SEED)

    assert first_path.read_bytes() == second_path.read_bytes()
    records = read_and_validate_csv(first_path)
    assert len(records) == 365 * len(PRODUCTS)
    assert min(record.date for record in records) == date(2024, 1, 1)


def test_russian_demo_profile_is_reproducible_and_valid(tmp_path) -> None:
    first_path = tmp_path / "ru_first.csv"
    second_path = tmp_path / "ru_second.csv"

    assert generate_demo_csv(first_path, seed=RU_DEMO_SEED, profile="ru") == 365 * len(RU_PRODUCTS)
    generate_demo_csv(second_path, seed=RU_DEMO_SEED, profile="ru")

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_text(encoding="utf-8").splitlines()[0] == "date,product,category,units_sold,revenue,price,discount_pct,ad_spend,promo"
    records = read_and_validate_csv(first_path)
    assert any(any("А" <= char <= "я" for char in record.product + record.category) for record in records)
    assert len(records) == 365 * len(RU_PRODUCTS)


def test_manual_acceptance_profile_is_reproducible_and_valid_without_db_import(tmp_path) -> None:
    first_path = tmp_path / "manual_first.csv"
    second_path = tmp_path / "manual_second.csv"
    rows_count = generate_demo_csv(first_path, seed=MANUAL_ACCEPTANCE_RU_SEED, profile="manual-acceptance-ru")
    generate_demo_csv(second_path, seed=MANUAL_ACCEPTANCE_RU_SEED, profile="manual-acceptance-ru")

    records = read_and_validate_csv(first_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert rows_count == 455 * len(MANUAL_ACCEPTANCE_RU_PRODUCTS)
    assert len(records) == rows_count
    assert min(record.date for record in records) == date(2023, 3, 1)
    assert max(record.date for record in records) == date(2024, 5, 28)
    assert any("Беговая дорожка" == record.product for record in records)
