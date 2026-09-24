import json

import pytest

from sales_forecast.ai.insights import (
    AIInsights,
    AIInsightsError,
    ProxyAIClient,
    SYSTEM_PROMPT,
    compact_payload,
)


def test_compact_payload_and_prompt():
 d={"kpis":{"total_revenue":1},"growth_trend":{},"rankings":{"top_products_by_revenue":[1,2,3,4]},"target_correlations":{}}
 f={"target":"revenue","forecast_points":[{"date":"x"},{"date":"y"}],"selected_model":"prophet"}
 p=compact_payload(d,f,None)
 assert "scenario" not in p and len(p["descriptive"]["top_products"])==3 and json.dumps(p)
 assert "Не придумывай числа" in SYSTEM_PROMPT and "причинность" in SYSTEM_PROMPT and "snake_case" in SYSTEM_PROMPT


def test_compact_payload_is_human_readable_without_changing_saved_results():
 d={"kpis":{"total_revenue":9202347.2},"growth_trend":{},"rankings":{"top_products_by_revenue":[{"share_of_revenue":0.35486197586633117}]},"target_correlations":{}}
 f={"target":"revenue","forecast_points":[],"selected_model":"prophet","model_comparison":{"prophet":{"mape":4.85234}}}
 s={"percent_difference":25.50066970895493,"metrics":{"r2":0.9077748988428024},"feature_importance":[{"importance":0.8758728996615303}]}
 p=compact_payload(d,f,s)
 assert p["descriptive"]["kpis"]["total_revenue"] == "9 202 347,20"
 assert p["descriptive"]["top_products"][0]["share_of_revenue"] == "35.49%"
 assert p["forecast"]["model_comparison"]["prophet"]["mape"] == "4.85%"
 assert p["scenario"]["percent_difference"] == "25.50%"
 assert p["scenario"]["metrics"]["r2"] == 0.908
 assert p["scenario"]["top_feature_importance"][0]["importance"] == 0.8759


def test_structured_response():
 result=AIInsights.model_validate({"summary":"s","key_insights":[],"forecast_commentary":"f","scenario_commentary":None,"recommendations":[],"risks":[]})
 assert result.summary=="s"


def test_schema_marks_optional_scenario_as_nullable_required():
 schema=AIInsights.model_json_schema()
 assert "scenario_commentary" in schema["properties"] and "scenario_commentary" in schema["required"]
 assert schema["additionalProperties"] is False
 assert {item["type"] for item in schema["properties"]["scenario_commentary"]["anyOf"]} == {"string", "null"}


class _FakeCompletions:
 def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
  self.content = content
  self.error = error
  self.kwargs: dict[str, object] | None = None

 def create(self, **kwargs: object) -> object:
  self.kwargs = kwargs
  if self.error:
   raise self.error
  return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": self.content})()})()]})()


def _client_with(completions: _FakeCompletions) -> ProxyAIClient:
 client = ProxyAIClient("test-key", "https://example.invalid/v1", "test-model")
 client.client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
 return client


def test_successful_structured_response_uses_strict_schema():
 completions = _FakeCompletions(json.dumps({"summary":"s","key_insights":[],"forecast_commentary":"f","scenario_commentary":None,"recommendations":[],"risks":[]}))
 result = _client_with(completions).generate({"descriptive": {}, "forecast": {}})
 assert result.summary == "s"
 assert completions.kwargs is not None
 response_format = completions.kwargs["response_format"]
 assert isinstance(response_format, dict)
 assert response_format["type"] == "json_schema"
 assert response_format["json_schema"]["strict"] is True


def test_invalid_structured_response_is_a_safe_domain_error():
 client = _client_with(_FakeCompletions('{"wrong": "shape"}'))
 with pytest.raises(AIInsightsError, match="AI returned an invalid structured response"):
  client.generate({})


def test_empty_content_is_reported_separately():
 client = _client_with(_FakeCompletions(None))
 with pytest.raises(AIInsightsError, match="AI returned an empty response"):
  client.generate({})


def test_api_error_does_not_expose_provider_message_to_cli():
 client = _client_with(_FakeCompletions(error=RuntimeError("bad schema; Authorization: secret-value")))
 with pytest.raises(AIInsightsError, match="ProxyAPI request failed: RuntimeError") as error:
  client.generate({})
 assert "secret-value" not in str(error.value)
 assert "bad schema" not in str(error.value)
