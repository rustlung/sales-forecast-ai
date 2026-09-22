"""Persistence operations for descriptive analysis executions."""

from __future__ import annotations

from sqlalchemy.orm import Session

from sales_forecast.database.models import AnalysisRun


class AnalysisRunRepository:
    def create_running(self, session: Session, dataset_id: int) -> AnalysisRun:
        run = AnalysisRun(dataset_id=dataset_id, analysis_type="descriptive", status="running")
        session.add(run)
        session.flush()
        return run

    def complete(self, session: Session, run_id: int, result_json: dict[str, object]) -> AnalysisRun:
        run = session.get(AnalysisRun, run_id)
        assert run is not None
        run.status = "completed"
        run.result_json = result_json
        run.error_message = None
        return run

    def fail(self, session: Session, run_id: int, message: str) -> None:
        run = session.get(AnalysisRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = message
