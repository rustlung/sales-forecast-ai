from sales_forecast.ui.presentation import (
    forecast_dataframe,
    format_correlation,
    format_currency,
    format_feature_importance,
    format_percent,
    localize_feature_name,
    localize_weekday,
    optional_text,
    russian_time_axis_ticks,
)


def test_formatting_helpers_are_human_readable() -> None:
    assert format_currency(9202347.2) == "9 202 347,20"
    assert format_percent(25.500669) == "25,50%"
    assert format_currency(float("nan")) == "—"


def test_analytical_formatting_and_localization() -> None:
    assert format_correlation(0.9077748988428024) == "0,9078"
    assert format_feature_importance(0.8758728996615303) == "0,8759"
    assert localize_weekday("Monday") == "Понедельник"
    assert localize_feature_name("numeric__ad_spend") == "Рекламные расходы"
    assert localize_feature_name("category__product_Wireless Headphones") == "Товар: Wireless Headphones"
    assert localize_feature_name("category__promo_True") == "Промо: да"


def test_russian_time_axis_ticks_keep_months_and_years() -> None:
    ticks, labels = russian_time_axis_ticks(["2024-01-02", "2024-03-15", "2025-01-05"])
    assert all(str(tick).startswith("20") for tick in ticks)
    assert labels == ["Янв 2024", "Мар 2024", "Янв 2025"]


def test_forecast_dataframe_removes_nan_presentation_rows() -> None:
    frame = forecast_dataframe(
        [
            {"date": "2025-01-02", "predicted": 20, "lower": None, "upper": 30},
            {"date": "bad", "predicted": 10, "lower": 0, "upper": 20},
            {"date": "2025-01-01", "predicted": float("nan"), "lower": 0, "upper": 20},
        ]
    )
    assert len(frame) == 1
    assert frame.iloc[0]["predicted"] == 20


def test_optional_scenario_commentary() -> None:
    assert optional_text(None) is None
    assert optional_text("  ") is None
    assert optional_text("Комментарий") == "Комментарий"
