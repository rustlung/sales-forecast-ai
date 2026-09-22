"""Deterministic descriptive analytics independent from persistence and UI."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from sales_forecast.database.models import Dataset, SalesRecord


NUMERIC_COLUMNS = ("units_sold", "revenue", "price", "discount_pct", "ad_spend")
CORRELATION_COLUMNS = ("units_sold", "revenue", "price", "discount_pct", "ad_spend", "promo")


@dataclass(frozen=True)
class DescriptiveAnalysisResult:
    dataset: dict[str, object]
    kpis: dict[str, object]
    growth_trend: dict[str, object]
    daily_series: list[dict[str, object]]
    weekly_series: list[dict[str, object]]
    monthly_series: list[dict[str, object]]
    by_product: list[dict[str, object]]
    by_category: list[dict[str, object]]
    rankings: dict[str, list[dict[str, object]]]
    weekday_seasonality: list[dict[str, object]]
    monthly_seasonality: list[dict[str, object]]
    correlation_matrix: dict[str, dict[str, float | None]]
    target_correlations: dict[str, dict[str, float | None]]

    def to_dict(self) -> dict[str, object]:
        return _json_safe(self.__dict__)


def prepare_dataframe(records: list[SalesRecord]) -> pd.DataFrame:
    """Convert ORM records to a sorted, analytics-ready DataFrame."""
    rows = [
        {
            "date": record.date,
            "product": record.product,
            "category": record.category,
            "units_sold": record.units_sold,
            "revenue": record.revenue,
            "price": record.price,
            "discount_pct": record.discount_pct,
            "ad_spend": record.ad_spend,
            "promo": record.promo,
        }
        for record in records
    ]
    dataframe = pd.DataFrame(rows, columns=["date", "product", "category", *NUMERIC_COLUMNS, "promo"])
    if dataframe.empty:
        dataframe["date"] = pd.to_datetime(dataframe["date"])
        for column in NUMERIC_COLUMNS:
            dataframe[column] = pd.Series(dtype="float64")
        dataframe["promo"] = pd.Series(dtype="bool")
        return dataframe
    dataframe["date"] = pd.to_datetime(dataframe["date"], errors="raise")
    for column in NUMERIC_COLUMNS:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="raise").astype("float64")
    dataframe["promo"] = dataframe["promo"].astype("bool")
    return dataframe.sort_values("date", kind="stable").reset_index(drop=True)


def analyze_dataset(dataset: Dataset, records: list[SalesRecord]) -> DescriptiveAnalysisResult:
    dataframe = prepare_dataframe(records)
    if dataframe.empty:
        raise ValueError("Dataset contains no sales records")
    daily = _daily_aggregate(dataframe)
    metadata = _metadata(dataset, dataframe)
    return DescriptiveAnalysisResult(
        dataset=metadata,
        kpis=_kpis(dataframe, daily, metadata),
        growth_trend=_growth_trend(daily),
        daily_series=_series_records(daily, "date", label="date"),
        weekly_series=_weekly_series(daily),
        monthly_series=_monthly_series(daily),
        by_product=_dimension_aggregate(dataframe, "product"),
        by_category=_dimension_aggregate(dataframe, "category"),
        rankings=_rankings(dataframe),
        weekday_seasonality=_weekday_seasonality(daily),
        monthly_seasonality=_monthly_seasonality(daily),
        correlation_matrix=_correlation_matrix(dataframe),
        target_correlations=_target_correlations(dataframe),
    )


def _metadata(dataset: Dataset, dataframe: pd.DataFrame) -> dict[str, object]:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "original_filename": dataset.original_filename,
        "date_from": dataframe["date"].min().date().isoformat(),
        "date_to": dataframe["date"].max().date().isoformat(),
        "rows_count": int(len(dataframe)),
    }


def _daily_aggregate(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe.groupby("date", as_index=False)[["revenue", "units_sold", "ad_spend"]].sum().sort_values("date")


def _kpis(dataframe: pd.DataFrame, daily: pd.DataFrame, metadata: dict[str, object]) -> dict[str, object]:
    total_revenue = float(dataframe["revenue"].sum())
    total_units = int(dataframe["units_sold"].sum())
    date_from = pd.Timestamp(metadata["date_from"])
    date_to = pd.Timestamp(metadata["date_to"])
    number_of_days = int((date_to - date_from).days + 1)
    promo_days = int(dataframe.loc[dataframe["promo"], "date"].nunique())
    return _json_safe(
        {
            "total_revenue": total_revenue,
            "total_units_sold": total_units,
            "average_daily_revenue": total_revenue / number_of_days,
            "average_daily_units": total_units / number_of_days,
            "average_recorded_price": float(dataframe["price"].mean()),
            "average_realized_revenue_per_unit": total_revenue / total_units if total_units else None,
            "average_discount_pct": float(dataframe["discount_pct"].mean()),
            "total_ad_spend": float(dataframe["ad_spend"].sum()),
            "promo_days": promo_days,
            "promo_share": promo_days / number_of_days,
            "promo_record_share": float(dataframe["promo"].mean()),
            "number_of_products": int(dataframe["product"].nunique()),
            "number_of_categories": int(dataframe["category"].nunique()),
            "date_from": metadata["date_from"],
            "date_to": metadata["date_to"],
            "number_of_days": number_of_days,
        }
    )


def _series_records(dataframe: pd.DataFrame, date_column: str, *, label: str = "period_start") -> list[dict[str, object]]:
    return [
        {
            label: row[date_column].date().isoformat(),
            "revenue": row["revenue"],
            "units_sold": int(round(row["units_sold"])),
            "ad_spend": row["ad_spend"],
        }
        for _, row in dataframe.iterrows()
    ]


def _weekly_series(daily: pd.DataFrame) -> list[dict[str, object]]:
    data = daily.assign(period_start=daily["date"] - pd.to_timedelta(daily["date"].dt.weekday, unit="D"))
    grouped = data.groupby("period_start", as_index=False)[["revenue", "units_sold", "ad_spend"]].sum()
    return _series_records(grouped, "period_start")


def _monthly_series(daily: pd.DataFrame) -> list[dict[str, object]]:
    data = daily.assign(period_start=daily["date"].dt.to_period("M").dt.to_timestamp())
    grouped = data.groupby("period_start", as_index=False)[["revenue", "units_sold", "ad_spend"]].sum()
    return _series_records(grouped, "period_start")


def _growth_trend(daily: pd.DataFrame) -> dict[str, object]:
    weekly = daily.assign(period_start=daily["date"] - pd.to_timedelta(daily["date"].dt.weekday, unit="D"))
    weekly = weekly.groupby("period_start", as_index=False)[["revenue", "units_sold"]].sum()
    last_date = daily["date"].max()
    week_ends = weekly["period_start"].dt.to_period("W-SUN").dt.end_time.dt.normalize()
    complete = weekly[week_ends <= last_date]
    growth: dict[str, object] = {"comparison_period": "weekly", "revenue_change_pct": None, "units_sold_change_pct": None}
    if len(complete) >= 2:
        previous, current = complete.iloc[-2], complete.iloc[-1]
        growth.update(
            {
                "previous_period_start": previous["period_start"].date().isoformat(),
                "current_period_start": current["period_start"].date().isoformat(),
                "revenue_change_pct": _percent_change(previous["revenue"], current["revenue"]),
                "units_sold_change_pct": _percent_change(previous["units_sold"], current["units_sold"]),
            }
        )
    slope = None
    if len(daily) >= 2:
        slope = float(np.polyfit(np.arange(len(daily)), daily["revenue"].to_numpy(dtype=float), 1)[0])
    growth["daily_revenue_linear_trend_slope"] = slope
    return _json_safe(growth)


def _percent_change(previous: float, current: float) -> float | None:
    return None if previous == 0 else (float(current) - float(previous)) / float(previous) * 100


def _dimension_aggregate(dataframe: pd.DataFrame, dimension: str) -> list[dict[str, object]]:
    grouped = dataframe.groupby(dimension, as_index=False).agg(
        revenue=("revenue", "sum"),
        units_sold=("units_sold", "sum"),
        average_price=("price", "mean"),
        average_discount_pct=("discount_pct", "mean"),
        total_ad_spend=("ad_spend", "sum"),
        promo_share=("promo", "mean"),
    )
    total_revenue = float(grouped["revenue"].sum())
    grouped["units_sold"] = grouped["units_sold"].round().astype(int)
    grouped["share_of_revenue"] = grouped["revenue"] / total_revenue if total_revenue else 0.0
    return _json_safe(grouped.sort_values("revenue", ascending=False).to_dict(orient="records"))


def _rankings(dataframe: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    products = _dimension_aggregate(dataframe, "product")
    categories = _dimension_aggregate(dataframe, "category")
    return {
        "top_products_by_revenue": products[:5],
        "bottom_products_by_revenue": list(reversed(products[-5:])),
        "top_categories_by_revenue": categories[:5],
        "bottom_categories_by_revenue": list(reversed(categories[-5:])),
    }


def _weekday_seasonality(daily: pd.DataFrame) -> list[dict[str, object]]:
    data = daily.assign(weekday=daily["date"].dt.weekday, weekday_name=daily["date"].dt.day_name())
    grouped = data.groupby(["weekday", "weekday_name"], as_index=False).agg(
        revenue_total=("revenue", "sum"),
        units_sold_total=("units_sold", "sum"),
        days_count=("date", "count"),
        average_daily_revenue=("revenue", "mean"),
        average_daily_units=("units_sold", "mean"),
    )
    grouped["units_sold_total"] = grouped["units_sold_total"].round().astype(int)
    return _json_safe(grouped.sort_values("weekday").to_dict(orient="records"))


def _monthly_seasonality(daily: pd.DataFrame) -> list[dict[str, object]]:
    data = daily.assign(month_start=daily["date"].dt.to_period("M").dt.to_timestamp())
    grouped = data.groupby("month_start", as_index=False).agg(
        revenue_total=("revenue", "sum"),
        units_sold_total=("units_sold", "sum"),
        days_count=("date", "count"),
        average_daily_revenue=("revenue", "mean"),
        average_daily_units=("units_sold", "mean"),
    )
    grouped["units_sold_total"] = grouped["units_sold_total"].round().astype(int)
    result = _json_safe(grouped.to_dict(orient="records"))
    for item in result:
        item["month_start"] = pd.Timestamp(item["month_start"]).date().isoformat()
    return result


def _correlation_matrix(dataframe: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    values = dataframe.assign(promo=dataframe["promo"].astype(int))[list(CORRELATION_COLUMNS)].corr(method="pearson")
    return {
        row_name: {column_name: _finite_float(values.loc[row_name, column_name]) for column_name in CORRELATION_COLUMNS}
        for row_name in CORRELATION_COLUMNS
    }


def _target_correlations(dataframe: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    matrix = _correlation_matrix(dataframe)
    features = ("price", "discount_pct", "ad_spend", "promo")
    return {target: {feature: matrix[target][feature] for feature in features} for target in ("revenue", "units_sold")}


def _finite_float(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _finite_float(value)
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float):
        return _finite_float(value)
    return value
