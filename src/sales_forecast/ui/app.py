"""Streamlit presentation layer for existing sales forecast services."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sales_forecast.ai.insights import AIInsightsError
from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine, create_session_factory
from sales_forecast.forecasting.errors import ForecastingError
from sales_forecast.logging_config import configure_logging
from sales_forecast.repositories.analysis_runs import AnalysisRunRepository
from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.repositories.forecasts import ForecastRepository
from sales_forecast.scenarios.modeling import ScenarioInput, ScenarioValidationError
from sales_forecast.services.ai_insights import AIInsightsService
from sales_forecast.services.dataset_analysis import DatasetAnalysisService
from sales_forecast.services.dataset_forecast import DatasetForecastService
from sales_forecast.services.dataset_scenario import DatasetScenarioService
from sales_forecast.ui.presentation import (
    forecast_dataframe,
    format_currency,
    format_correlation,
    format_feature_importance,
    format_metric,
    format_number,
    format_percent,
    localize_feature_name,
    localize_weekday,
    optional_text,
    russian_time_axis_ticks,
)


logger = logging.getLogger(__name__)

st.set_page_config(page_title="Sales Forecast AI", page_icon="📈", layout="wide")


@st.cache_resource
def session_factory(database_url: str):
    """Cache the engine/session factory, never an open mutable database session."""

    return create_session_factory(create_engine(database_url))


@st.cache_data(ttl=30)
def dataset_options(database_url: str) -> list[dict[str, Any]]:
    factory = session_factory(database_url)
    with factory() as session:
        return [
            {
                "id": dataset.id,
                "name": dataset.name,
                "date_from": dataset.date_from.isoformat() if dataset.date_from else None,
                "date_to": dataset.date_to.isoformat() if dataset.date_to else None,
                "rows_count": dataset.rows_count,
            }
            for dataset in DatasetRepository().list_all(session)
        ]


def latest_result(factory, dataset_id: int, analysis_type: str) -> dict[str, Any] | None:
    with factory() as session:
        run = AnalysisRunRepository().latest_completed(session, dataset_id, analysis_type)
        return dict(run.result_json) if run and run.result_json else None


def latest_forecast(factory, dataset_id: int, target: str) -> dict[str, Any] | None:
    with factory() as session:
        forecast = ForecastRepository().latest_for_target(session, dataset_id, target)
        return dict(forecast.forecast_json) if forecast else None


def product_records(factory, dataset_id: int) -> list[dict[str, Any]]:
    with factory() as session:
        return [
            {
                "date": record.date,
                "product": record.product,
                "category": record.category,
                "price": float(record.price),
                "discount_pct": float(record.discount_pct),
                "ad_spend": float(record.ad_spend),
                "promo": bool(record.promo),
            }
            for record in DatasetRepository().get_sales_records(session, dataset_id)
        ]


def show_error(error: Exception) -> None:
    expected = (AIInsightsError, ForecastingError, ScenarioValidationError, ValueError)
    if isinstance(error, expected):
        st.error(str(error))
        return
    logger.exception("Unexpected dashboard error")
    st.error("Операция не выполнена. Проверьте данные и логи приложения.")


def figure_layout(figure: go.Figure, title: str, x_title: str, y_title: str, time_values: object | None = None) -> go.Figure:
    figure.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, margin=dict(l=20, r=20, t=55, b=20))
    if time_values is not None:
        tickvals, ticktext = russian_time_axis_ticks(time_values)
        figure.update_xaxes(tickvals=tickvals, ticktext=ticktext, hoverformat="%d.%m.%Y")
    return figure


def render_overview(factory, dataset_id: int, descriptive: dict[str, Any] | None) -> None:
    st.subheader("Обзор")
    if descriptive is None:
        st.info("Для выбранного датасета ещё нет завершённого описательного анализа.")
        if st.button("Запустить анализ", type="primary", key="run_analysis"):
            try:
                with st.spinner("Выполняется описательный анализ…"):
                    DatasetAnalysisService(factory).analyze(dataset_id)
                st.cache_data.clear()
                st.success("Анализ завершён.")
                st.rerun()
            except Exception as error:
                show_error(error)
        return

    kpis = descriptive.get("kpis", {})
    cards = [
        ("Выручка", format_currency(kpis.get("total_revenue"))),
        ("Продажи, шт.", format_number(kpis.get("total_units_sold"))),
        ("Средняя дневная выручка", format_currency(kpis.get("average_daily_revenue"))),
        ("Средние дневные продажи", format_number(kpis.get("average_daily_units"), 2)),
        ("Средняя скидка", format_percent(kpis.get("average_discount_pct"))),
        ("Рекламные расходы", format_currency(kpis.get("total_ad_spend"))),
        ("Товаров", format_number(kpis.get("number_of_products"))),
        ("Категорий", format_number(kpis.get("number_of_categories"))),
    ]
    for row in (cards[:4], cards[4:]):
        columns = st.columns(4)
        for column, (label, value) in zip(columns, row, strict=True):
            column.metric(label, value)

    daily = pd.DataFrame(descriptive.get("daily_series", []))
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"])
        figure = go.Figure(go.Scatter(x=daily["date"], y=daily["revenue"], mode="lines", name="Выручка", hovertemplate="Дата: %{x|%d.%m.%Y}<br>Выручка: %{y}<extra></extra>"))
        st.plotly_chart(figure_layout(figure, "Дневная выручка", "Дата", "Выручка", daily["date"]), width="stretch")


def render_analytics(descriptive: dict[str, Any] | None) -> None:
    st.subheader("Аналитика")
    if descriptive is None:
        st.info("Сначала запустите описательный анализ на вкладке «Обзор».")
        return

    product = pd.DataFrame(descriptive.get("by_product", [])).sort_values("revenue", ascending=True)
    category = pd.DataFrame(descriptive.get("by_category", [])).sort_values("revenue", ascending=True)
    left, right = st.columns(2)
    with left:
        if not product.empty:
            figure = go.Figure(go.Bar(x=product["revenue"], y=product["product"], orientation="h"))
            st.plotly_chart(figure_layout(figure, "Выручка по товарам", "Выручка", "Товар"), width="stretch")
    with right:
        if not category.empty:
            figure = go.Figure(go.Bar(x=category["revenue"], y=category["category"], orientation="h"))
            st.plotly_chart(figure_layout(figure, "Выручка по категориям", "Выручка", "Категория"), width="stretch")

    weekday = pd.DataFrame(descriptive.get("weekday_seasonality", [])).sort_values("weekday")
    monthly = pd.DataFrame(descriptive.get("monthly_seasonality", []))
    left, right = st.columns(2)
    with left:
        if not weekday.empty:
            figure = go.Figure()
            weekday["weekday_label"] = weekday["weekday_name"].map(localize_weekday)
            figure.add_bar(x=weekday["weekday_label"], y=weekday["average_daily_revenue"], name="Выручка")
            figure.add_scatter(x=weekday["weekday_label"], y=weekday["average_daily_units"], mode="lines+markers", name="Продажи, шт.", yaxis="y2")
            figure.update_layout(yaxis2=dict(overlaying="y", side="right", title="Продажи, шт."))
            st.plotly_chart(figure_layout(figure, "Сезонность по дням недели", "День недели", "Средняя дневная выручка"), width="stretch")
    with right:
        if not monthly.empty:
            monthly["month_start"] = pd.to_datetime(monthly["month_start"])
            figure = go.Figure(go.Bar(x=monthly["month_start"], y=monthly["average_daily_revenue"], hovertemplate="Месяц: %{x|%m.%Y}<br>Средняя дневная выручка: %{y}<extra></extra>"))
            st.plotly_chart(figure_layout(figure, "Месячная сезонность", "Месяц", "Средняя дневная выручка", monthly["month_start"]), width="stretch")
            st.caption("Показано среднее дневное значение, а не суммарная выручка месяца.")

    correlation = pd.DataFrame(descriptive.get("correlation_matrix", {})).reindex(
        ["units_sold", "revenue", "price", "discount_pct", "ad_spend", "promo"]
    )
    if not correlation.empty:
        labels = {"units_sold": "Продажи, шт.", "revenue": "Выручка", "price": "Цена", "discount_pct": "Скидка", "ad_spend": "Рекламные расходы", "promo": "Промо"}
        hover = [[format_correlation(value) for value in row] for row in correlation.to_numpy()]
        figure = go.Figure(go.Heatmap(z=correlation.to_numpy(), text=hover, hovertemplate="%{text}<extra></extra>", x=[labels.get(value, value) for value in correlation.columns], y=[labels.get(value, value) for value in correlation.index], colorscale="RdBu", zmin=-1, zmax=1, hoverongaps=False))
        st.plotly_chart(figure_layout(figure, "Корреляции признаков", "Признак", "Признак"), width="stretch")
    st.warning("Корреляция не означает причинность.")


def render_forecast(factory, dataset_id: int, descriptive: dict[str, Any] | None) -> None:
    st.subheader("Прогноз")
    controls = st.columns(2)
    target = controls[0].selectbox("Целевой показатель", ("revenue", "units_sold"), format_func=lambda value: "Выручка" if value == "revenue" else "Продажи, шт.")
    horizon = controls[1].selectbox("Горизонт, дней", (7, 30, 90), index=1)
    if st.button("Построить прогноз", type="primary", key="run_forecast"):
        try:
            with st.spinner("Обучение и валидация моделей…"):
                DatasetForecastService(factory).forecast(dataset_id, target, horizon)
            st.success("Прогноз сохранён.")
            st.rerun()
        except Exception as error:
            show_error(error)

    forecast = latest_forecast(factory, dataset_id, target)
    if forecast is None:
        st.info("Сохранённого прогноза для этого показателя пока нет.")
        return

    comparison = forecast.get("model_comparison", {})
    selected = forecast.get("selected_model", "—")
    st.metric("Выбранная модель", str(selected).replace("_", " ").title())
    metrics = pd.DataFrame([
        {"Модель": name.replace("_", " ").title(), "MAE": format_metric(values.get("mae"), "mae"), "RMSE": format_metric(values.get("rmse"), "rmse"), "MAPE": format_metric(values.get("mape"), "mape")}
        for name, values in comparison.items()
    ])
    if not metrics.empty:
        st.dataframe(metrics, hide_index=True, width="stretch")
    validation = forecast.get("validation", {})
    st.caption(f"Валидация: {validation.get('date_from', '—')} — {validation.get('date_to', '—')}; критерий выбора: {forecast.get('selection_metric', '—').upper()}")

    figure = go.Figure()
    if descriptive:
        history = pd.DataFrame(descriptive.get("daily_series", []))
        value_column = "revenue" if target == "revenue" else "units_sold"
        if not history.empty:
            figure.add_scatter(x=pd.to_datetime(history["date"]), y=history[value_column], mode="lines", name="История")
    points = forecast_dataframe(forecast.get("forecast_points", []))
    if not points.empty:
        figure.add_scatter(x=points["date"], y=points["predicted"], mode="lines", name="Прогноз", line=dict(dash="dash"))
        intervals = points.dropna(subset=["lower", "upper"])
        if not intervals.empty:
            figure.add_scatter(x=intervals["date"], y=intervals["upper"], mode="lines", line=dict(width=0), showlegend=False)
            figure.add_scatter(x=intervals["date"], y=intervals["lower"], mode="lines", fill="tonexty", fillcolor="rgba(37,99,235,0.15)", line=dict(width=0), name="Интервал Prophet")
    label = "Выручка" if target == "revenue" else "Продажи, шт."
    dates = []
    if descriptive and not history.empty:
        dates.extend(pd.to_datetime(history["date"]).tolist())
    if not points.empty:
        dates.extend(points["date"].tolist())
    st.plotly_chart(figure_layout(figure, f"{label}: история и прогноз", "Дата", label, dates), width="stretch")


def render_scenarios(factory, dataset_id: int) -> None:
    st.subheader("Сценарии")
    records = product_records(factory, dataset_id)
    if not records:
        st.info("В датасете нет записей для сценарного анализа.")
        return
    products = sorted({str(row["product"]) for row in records})
    product = st.selectbox("Товар", products)
    categories = sorted({str(row["category"]) for row in records if row["product"] == product})
    category = st.selectbox("Категория", categories)
    defaults = sorted((row for row in records if row["product"] == product and row["category"] == category), key=lambda row: row["date"])[-1]
    columns = st.columns(3)
    scenario_date = columns[0].date_input("Дата сценария", value=date.today())
    price = columns[1].number_input("Цена", min_value=0.01, value=float(defaults["price"]), step=0.01)
    discount = columns[2].number_input("Скидка, %", min_value=0.0, max_value=100.0, value=float(defaults["discount_pct"]), step=1.0)
    ad_spend = st.number_input("Рекламные расходы", min_value=0.0, value=float(defaults["ad_spend"]), step=1.0)
    promo = st.checkbox("Промо", value=bool(defaults["promo"]))
    if st.button("Рассчитать сценарий", type="primary", key="run_scenario"):
        try:
            scenario = ScenarioInput(product, category, scenario_date, float(price), float(discount), float(ad_spend), promo)
            with st.spinner("Обучение Random Forest и расчёт сценария…"):
                DatasetScenarioService(factory).run(dataset_id, scenario)
            st.success("Сценарий сохранён.")
            st.rerun()
        except Exception as error:
            show_error(error)

    scenario_result = latest_result(factory, dataset_id, "scenario")
    if scenario_result is None:
        st.info("Сохранённого сценария пока нет.")
        return
    columns = st.columns(4)
    columns[0].metric("Базовый сценарий", format_currency(scenario_result.get("baseline_predicted_revenue")))
    columns[1].metric("Сценарий", format_currency(scenario_result.get("scenario_predicted_revenue")))
    columns[2].metric("Изменение", format_currency(scenario_result.get("absolute_difference")))
    columns[3].metric("Изменение, %", format_percent(scenario_result.get("percent_difference")))
    comparison = go.Figure(go.Bar(x=["Базовый сценарий", "Сценарий"], y=[scenario_result.get("baseline_predicted_revenue"), scenario_result.get("scenario_predicted_revenue")]))
    st.plotly_chart(figure_layout(comparison, "Сравнение ожидаемой выручки", "", "Выручка"), width="stretch")
    metric_values = scenario_result.get("metrics", {})
    st.caption(f"MAE: {format_metric(metric_values.get('mae'), 'mae')} · RMSE: {format_metric(metric_values.get('rmse'), 'rmse')} · R²: {format_metric(metric_values.get('r2'), 'r2')}")
    importance = pd.DataFrame(scenario_result.get("feature_importance", [])[:10]).sort_values("importance", ascending=True)
    if not importance.empty:
        importance["feature_label"] = importance["feature"].map(localize_feature_name)
        importance["importance_label"] = importance["importance"].map(format_feature_importance)
        figure = go.Figure(go.Bar(x=importance["importance"], y=importance["feature_label"], orientation="h", text=importance["importance_label"], hovertemplate="%{y}: %{text}<extra></extra>"))
        st.plotly_chart(figure_layout(figure, "Важность признаков", "Важность", "Признак"), width="stretch")
    st.warning("Модель отражает статистические закономерности в исторических данных, не доказывает причинно-следственную связь и не гарантирует фактический эффект изменения цены, скидки, рекламы или промо.")


def render_ai_insights(factory, settings, dataset_id: int) -> None:
    st.subheader("AI-инсайты")
    insights = latest_result(factory, dataset_id, "ai_insights")
    if insights is None:
        st.info("Сохранённых AI-инсайтов пока нет.")
        if st.button("Сгенерировать AI-инсайты", type="primary", key="run_ai"):
            try:
                with st.spinner("ProxyAPI формирует AI-инсайты…"):
                    AIInsightsService(factory, settings).generate(dataset_id, "revenue")
                st.success("AI-инсайты сохранены.")
                st.rerun()
            except Exception as error:
                show_error(error)
        return
    ai_result = insights.get("ai_result", {})
    st.caption(f"Модель: {insights.get('model_name', '—')}")
    st.markdown("#### Резюме")
    st.write(ai_result.get("summary", "—"))
    for title, key in (("Ключевые инсайты", "key_insights"), ("Рекомендации", "recommendations"), ("Риски", "risks")):
        st.markdown(f"#### {title}")
        for item in ai_result.get(key, []):
            st.write(f"• {item}")
    st.markdown("#### Комментарий к прогнозу")
    st.write(ai_result.get("forecast_commentary", "—"))
    scenario_commentary = optional_text(ai_result.get("scenario_commentary"))
    if scenario_commentary:
        st.markdown("#### Комментарий к сценарию")
        st.write(scenario_commentary)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    factory = session_factory(settings.database_url)
    st.title("Sales Forecast AI")
    st.caption("Детерминированная аналитика, прогноз и сценарии на исторических продажах.")

    try:
        datasets = dataset_options(settings.database_url)
    except Exception:
        logger.exception("Could not load dashboard datasets")
        st.error("Не удалось подключиться к PostgreSQL. Проверьте DATABASE_URL и состояние базы данных.")
        return
    if not datasets:
        st.sidebar.warning("Датасеты пока отсутствуют.")
        st.info("Импортируйте CSV существующей CLI-командой, затем обновите страницу.")
        return

    by_id = {int(item["id"]): item for item in datasets}
    current_id = st.session_state.get("dataset_id")
    index = list(by_id).index(current_id) if current_id in by_id else 0
    dataset_id = st.sidebar.selectbox("Датасет", list(by_id), index=index, format_func=lambda item: f"#{item} — {by_id[item]['name']}")
    st.session_state["dataset_id"] = dataset_id
    selected = by_id[dataset_id]
    st.sidebar.markdown("### Метаданные")
    st.sidebar.write(f"**Название:** {selected['name']}")
    st.sidebar.write(f"**Период:** {selected['date_from'] or '—'} — {selected['date_to'] or '—'}")
    st.sidebar.write(f"**Строк:** {format_number(selected['rows_count'])}")

    try:
        descriptive = latest_result(factory, dataset_id, "descriptive")
        tabs = st.tabs(["Обзор", "Аналитика", "Прогноз", "Сценарии", "AI-инсайты"])
        with tabs[0]:
            render_overview(factory, dataset_id, descriptive)
        with tabs[1]:
            render_analytics(descriptive)
        with tabs[2]:
            render_forecast(factory, dataset_id, descriptive)
        with tabs[3]:
            render_scenarios(factory, dataset_id)
        with tabs[4]:
            render_ai_insights(factory, settings, dataset_id)
    except Exception as error:
        show_error(error)


if __name__ == "__main__":
    main()
