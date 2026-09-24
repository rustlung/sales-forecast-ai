from __future__ import annotations
import json
import logging
import math
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты аналитический ассистент. Отвечай только по переданным данным и на русском языке.
Используй только предоставленные системой результаты. Не придумывай числа и не пересчитывай KPI,
forecast или scenario. Не утверждай причинность по корреляциям или importance. Scenario estimate
не является гарантией. Явно отмечай ограничения и слабое качество метрик. Не называй скидку или
рекламный бюджет оптимальными, если это не вычислено системой. Не используй snake_case и имена
полей в тексте: вместо promo_share пиши «доля промодней», вместо share_of_revenue — «доля выручки».
Повторяй предоставленные отформатированные числа буквально: в русском тексте используй пробелы
между тысячами и запятую для дробной части, не выводи 10–15 знаков после запятой; доли, которые
являются share, описывай в процентах.
Верни только JSON по заданной схеме."""


class AIInsights(BaseModel):
    """Strict response contract returned by the LLM."""

    # Strict Structured Outputs requires this on every object in the response schema.
    # This model has no nested object models, so setting it here covers all objects.
    model_config = ConfigDict(extra="forbid")

    summary: str
    key_insights: list[str]
    forecast_commentary: str
    scenario_commentary: str | None
    recommendations: list[str]
    risks: list[str]


class AIInsightsError(Exception):
    """A safe domain error which can be shown by the CLI."""


def compact_payload(descriptive: dict[str, Any], forecast: dict[str, Any], scenario: dict[str, Any] | None) -> dict[str, Any]:
    payload={"descriptive":{"kpis":descriptive.get("kpis"),"growth_trend":descriptive.get("growth_trend"),"top_products":descriptive.get("rankings",{}).get("top_products_by_revenue",[])[:3],"top_categories":descriptive.get("rankings",{}).get("top_categories_by_revenue",[])[:3],"target_correlations":descriptive.get("target_correlations")},"forecast":{"target":forecast.get("target"),"selected_model":forecast.get("selected_model"),"validation":forecast.get("validation"),"model_comparison":forecast.get("model_comparison"),"horizon_days":forecast.get("horizon_days"),"first_forecast":(forecast.get("forecast_points") or [None])[0],"last_forecast":(forecast.get("forecast_points") or [None])[-1]}}
    if scenario: payload["scenario"]={key:scenario.get(key) for key in ("baseline_input","scenario_input","baseline_predicted_revenue","scenario_predicted_revenue","absolute_difference","percent_difference","metrics","disclaimer")}; payload["scenario"]["top_feature_importance"]=scenario.get("feature_importance",[])[:5]
    return _humanize_payload(payload)


def _humanize_payload(value: Any, key: str | None = None) -> Any:
    """Round only the compact LLM input, never stored analytical results."""
    if isinstance(value, dict):
        return {item_key: _humanize_payload(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_humanize_payload(item, key) for item in value]
    if not isinstance(value, float) or not math.isfinite(value):
        return value
    if key in {"share_of_revenue", "promo_share"}:
        return f"{value * 100:.2f}%"
    if key in {"discount_pct", "percent_difference", "mape"}:
        return f"{value:.2f}%"
    if key == "r2":
        return round(value, 3)
    if key == "importance":
        return round(value, 4)
    if key in {
        "revenue", "ad_spend", "price", "mae", "rmse", "predicted", "lower", "upper",
        "total_revenue", "average_daily_revenue", "total_ad_spend", "average_recorded_price",
        "average_realized_revenue_per_unit", "baseline_predicted_revenue",
        "scenario_predicted_revenue", "absolute_difference",
    }:
        return _russian_decimal(value, 2)
    return round(value, 2)


def _russian_decimal(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def _provider_error_label(error: Exception) -> str:
    """Return the minimal provider error identifier suitable for CLI output."""

    status_code = getattr(error, "status_code", None)

    details = type(error).__name__
    if status_code is not None:
        details += f" (HTTP {status_code})"
    return details


class ProxyAIClient:
    def __init__(self, api_key: str | None, base_url: str | None, model: str | None) -> None:
        if not api_key: raise AIInsightsError("OPENAI_API_KEY is not configured")
        if not model: raise AIInsightsError("OPENAI_MODEL is not configured")
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=120,
            max_retries=1,
        )
        self.model = model

    def generate(self, payload: dict[str, Any]) -> AIInsights:
        serialized = json.dumps(payload, ensure_ascii=False)
        logger.debug("Sending compact AI insights payload: %s chars", len(serialized))
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_schema", "json_schema": {"name": "ai_insights", "strict": True, "schema": AIInsights.model_json_schema()}},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": "Подготовь аналитические инсайты на основе следующих уже рассчитанных системой данных. Не пересчитывай показатели, не добавляй отсутствующие числа и верни результат строго в заданной JSON-схеме. Если блока scenario нет, верни scenario_commentary как null.\n\n" + serialized,
                    },
                ],
            )
        except Exception as error:
            error_label = _provider_error_label(error)
            logger.error("ProxyAPI request failed: %s", error_label)
            raise AIInsightsError(f"ProxyAPI request failed: {error_label}") from error

        content = response.choices[0].message.content or ""

        if not content:
            raise AIInsightsError("AI returned an empty response")

        try:
            return AIInsights.model_validate_json(content)
        except ValidationError as error:
            logger.error("AI structured response validation failed: %s", error.errors())
            raise AIInsightsError(
                "AI returned an invalid structured response"
            ) from error

    
