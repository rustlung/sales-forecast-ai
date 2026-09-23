from __future__ import annotations
import argparse
from datetime import date
from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine, create_session_factory
from sales_forecast.logging_config import configure_logging
from sales_forecast.repositories.datasets import DatasetNotFoundError
from sales_forecast.scenarios.modeling import ScenarioInput, ScenarioValidationError
from sales_forecast.services.dataset_scenario import DatasetScenarioService

def _bool(value: str) -> bool:
    if value.lower() in {"true","1","yes"}: return True
    if value.lower() in {"false","0","no"}: return False
    raise argparse.ArgumentTypeError("promo must be true or false")
def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("dataset_id",type=int); p.add_argument("--product",required=True); p.add_argument("--category",required=True); p.add_argument("--date",type=date.fromisoformat,required=True); p.add_argument("--price",type=float,required=True); p.add_argument("--discount",type=float,required=True); p.add_argument("--ad-spend",type=float,required=True); p.add_argument("--promo",type=_bool,required=True); a=p.parse_args()
    configure_logging(get_settings().log_level)
    try:
        result=DatasetScenarioService(create_session_factory(create_engine(get_settings().database_url))).run(a.dataset_id, ScenarioInput(a.product,a.category,a.date,a.price,a.discount,a.ad_spend,a.promo))
    except (DatasetNotFoundError,ScenarioValidationError) as e: print(f"Scenario failed: {e}"); raise SystemExit(2)
    r=result.result; m=r["metrics"]; top=r["feature_importance"][:5]
    print(f"analysis_run_id={result.analysis_run_id} model=random_forest MAE={m['mae']:.2f} RMSE={m['rmse']:.2f} R2={m['r2']} baseline={r['baseline_predicted_revenue']:.2f} scenario={r['scenario_predicted_revenue']:.2f} difference={r['absolute_difference']:.2f} pct={r['percent_difference']}")
    print("top_features=" + ", ".join(f"{x['feature']}:{x['importance']:.3f}" for x in top)); print(r["disclaimer"])
if __name__ == "__main__": main()
