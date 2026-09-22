from datetime import date
from decimal import Decimal

import pytest

from sales_forecast.services.csv_validation import CsvValidationError, read_and_validate_csv


HEADER = "date,product,category,units_sold,revenue,price,discount_pct,ad_spend,promo\n"
VALID_ROW = "2025-01-02, Product A , Category A ,12,100.50,10.00,5,20.25,YES\n"


def _write_csv(tmp_path, content: str):
    path = tmp_path / "sales.csv"
    path.write_text(content, encoding="utf-8")
    return path


def test_normalizes_types_boolean_whitespace_and_ignores_blank_rows(tmp_path) -> None:
    path = _write_csv(tmp_path, HEADER + VALID_ROW + ",,,,,,,,,\n")

    record = read_and_validate_csv(path)[0]

    assert record.date == date(2025, 1, 2)
    assert record.product == "Product A"
    assert record.category == "Category A"
    assert record.units_sold == 12
    assert record.revenue == Decimal("100.50")
    assert record.promo is True


@pytest.mark.parametrize(
    ("content", "field", "reason"),
    [
        ("date,product,category,units_sold,revenue,price,discount_pct,ad_spend\n", "promo", "required column is missing"),
        (HEADER + "2025-01-02,Product A,Category A,nope,100,10,0,0,false\n", "units_sold", "expected a decimal number"),
        (HEADER + "2025-01-02,Product A,Category A,1,100,10,101,0,false\n", "discount_pct", "must be at most 100"),
        (HEADER + "not-a-date,Product A,Category A,1,100,10,0,0,false\n", "date", "expected ISO date"),
    ],
)
def test_rejects_invalid_csv_values(tmp_path, content: str, field: str, reason: str) -> None:
    path = _write_csv(tmp_path, content)

    with pytest.raises(CsvValidationError) as error:
        read_and_validate_csv(path)

    assert f"field '{field}'" in str(error.value)
    assert reason in str(error.value)
