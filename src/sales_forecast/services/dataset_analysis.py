"""Application service orchestrating persistence and descriptive analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from sales_forecast.analytics.descriptive import analyze_dataset
from sales_forecast.repositories.analysis_runs import AnalysisRunRepository
from sales_forecast.repositories.datasets import DatasetNotFoundError, DatasetRepository


logger = logging.getLogger(__name__)
SAFE_ANALYSIS_FAILURE = "Analysis failed. Check dataset data and application logs."


@dataclass(frozen=True)
class AnalysisExecution:
    analysis_run_id: int
    result: dict[str, object]


class DatasetAnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        datasets: DatasetRepository | None = None,
        analysis_runs: AnalysisRunRepository | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._datasets = datasets or DatasetRepository()
        self._analysis_runs = analysis_runs or AnalysisRunRepository()

    def analyze(self, dataset_id: int) -> AnalysisExecution:
        with self._session_factory() as session:
            self._datasets.get_by_id(session, dataset_id)

        with self._session_factory() as session:
            with session.begin():
                run = self._analysis_runs.create_running(session, dataset_id)
                run_id = run.id
        assert run_id is not None

        try:
            with self._session_factory() as session:
                dataset = self._datasets.get_by_id(session, dataset_id)
                records = self._datasets.get_sales_records(session, dataset_id)
                result = analyze_dataset(dataset, records).to_dict()
            with self._session_factory() as session:
                with session.begin():
                    self._analysis_runs.complete(session, run_id, result)
            return AnalysisExecution(analysis_run_id=run_id, result=result)
        except Exception:
            logger.error("Descriptive analysis failed for dataset_id=%s", dataset_id)
            with self._session_factory() as session:
                with session.begin():
                    self._analysis_runs.fail(session, run_id, SAFE_ANALYSIS_FAILURE)
            raise
