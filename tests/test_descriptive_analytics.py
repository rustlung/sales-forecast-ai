import json
from datetime import date
from decimal import Decimal

from sales_forecast.analytics.descriptive import analyze_dataset, prepare_dataframe
from sales_forecast.database.models import Dataset, SalesRecord


def _record(
    record_date: date,
    product: str,
    category: str,
    units: int,
    revenue: str,
    price: str,
    discount: str,
    ad_spend: str,
    promo: bool,
) -> SalesRecord:
    return SalesRecord(
        dataset_id=1,
        date=record_date,
        product=product,
        category=category,
        units_sold=units,
        revenue=Decimal(revenue),
        price=Decimal(price),
        discount_pct=Decimal(discount),
        ad_spend=Decimal(ad_spend),
        promo=promo,
    )


def _fixture_records() -> list[SalesRecord]:
    return [
        _record(date(2025, 1, 27), "Alpha", "A", 10, "100", "10", "0", "5", False),
        _record(date(2025, 1, 28), "Alpha", "A", 20, "180", "10", "10", "10", True),
        _record(date(2025, 2, 1), "Beta", "B", 5, "75", "15", "0", "3", False),
        _record(date(2025, 2, 2), "Beta", "B", 10, "135", "15", "10", "3", True),
        _record(date(2025, 2, 3), "Alpha", "A", 15, "150", "10", "0", "6", False),
        _record(date(2025, 2, 9), "Beta", "B", 10, "150", "15", "0", "4", False),
    ]


def _dataset() -> Dataset:
    return Dataset(id=1, name="Fixture", original_filename="fixture.csv", date_from=date(2025, 1, 27), date_to=date(2025, 2, 9), rows_count=6)


def test_dataframe_preparation_has_canonical_columns_types_and_order() -> None:
    dataframe = prepare_dataframe(list(reversed(_fixture_records())))

    assert list(dataframe.columns) == ["date", "product", "category", "units_sold", "revenue", "price", "discount_pct", "ad_spend", "promo"]
    assert str(dataframe["date"].dtype).startswith("datetime64")
    assert str(dataframe["revenue"].dtype) == "float64"
    assert dataframe["promo"].dtype == bool
    assert dataframe["date"].is_monotonic_increasing


def test_kpis_series_dimensions_and_seasonality() -> None:
    result = analyze_dataset(_dataset(), _fixture_records()).to_dict()

    assert result["kpis"]["total_revenue"] == 790.0
    assert result["kpis"]["total_units_sold"] == 70
    assert result["kpis"]["number_of_days"] == 14
    assert len(result["daily_series"]) == 6
    assert len(result["weekly_series"]) == 2
    assert len(result["monthly_series"]) == 2
    assert result["by_product"][0]["product"] == "Alpha"
    assert result["by_category"][0]["category"] == "A"
    assert [item["weekday"] for item in result["weekday_seasonality"]] == [0, 1, 5, 6]
    february = next(item for item in result["monthly_seasonality"] if item["month_start"] == "2025-02-01")
    assert february["days_count"] == 4
    assert february["average_daily_revenue"] == 127.5


def test_correlations_constant_columns_and_json_output_are_safe() -> None:
    records = [
        _record(date(2025, 1, 1), "A", "Only", 1, "10", "10", "0", "1", False),
        _record(date(2025, 1, 2), "A", "Only", 2, "20", "10", "0", "1", False),
    ]
    result = analyze_dataset(_dataset(), records).to_dict()

    assert result["correlation_matrix"]["revenue"]["price"] is None
    assert result["target_correlations"]["units_sold"]["promo"] is None
    json.dumps(result)
