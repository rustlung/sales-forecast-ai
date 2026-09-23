from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker
from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.repositories.analysis_runs import AnalysisRunRepository
from sales_forecast.scenarios.modeling import ScenarioInput, baseline_for, predict, prepare_ml_frame, train_and_evaluate

SAFE_FAILURE = "Scenario analysis failed. Check input data and application logs."
DISCLAIMER = "The model reflects statistical patterns in historical data; it does not prove causation and does not guarantee the actual effect of price, discount, advertising, or promo changes."

@dataclass(frozen=True)
class ScenarioExecution:
    analysis_run_id: int
    result: dict[str, object]

class DatasetScenarioService:
    def __init__(self, factory: sessionmaker[Session], datasets: DatasetRepository | None = None, runs: AnalysisRunRepository | None = None) -> None:
        self.factory, self.datasets, self.runs = factory, datasets or DatasetRepository(), runs or AnalysisRunRepository()

    def run(self, dataset_id: int, scenario: ScenarioInput) -> ScenarioExecution:
        with self.factory() as session:
            self.datasets.get_by_id(session, dataset_id)
            records = self.datasets.get_sales_records(session, dataset_id)
        with self.factory() as session:
            with session.begin():
                run = self.runs.create_running(session, dataset_id, "scenario")
                run_id = run.id
        assert run_id is not None
        try:
            frame = prepare_ml_frame(records); scenario.validate(frame)
            pipeline, metrics, importance, train, test = train_and_evaluate(frame)
            baseline = baseline_for(frame, scenario)
            base_value, scenario_value = predict(pipeline, baseline), predict(pipeline, scenario)
            result = {"dataset_id": dataset_id, "model_name": "random_forest", "target": "revenue",
                "train_period": {"date_from": train.date.min().date().isoformat(), "date_to": train.date.max().date().isoformat()},
                "test_period": {"date_from": test.date.min().date().isoformat(), "date_to": test.date.max().date().isoformat()},
                "train_rows": len(train), "test_rows": len(test), "metrics": metrics,
                "feature_importance": [{"feature": key, "importance": value} for key, value in importance.items()],
                "baseline_input": baseline.row(), "baseline_predicted_revenue": base_value,
                "scenario_input": scenario.row(), "scenario_predicted_revenue": scenario_value,
                "absolute_difference": scenario_value-base_value,
                "percent_difference": None if base_value == 0 else (scenario_value-base_value)/base_value*100,
                "disclaimer": DISCLAIMER}
            with self.factory() as session:
                with session.begin(): self.runs.complete(session, run_id, result)
            return ScenarioExecution(run_id, result)
        except Exception:
            with self.factory() as session:
                with session.begin(): self.runs.fail(session, run_id, SAFE_FAILURE)
            raise
