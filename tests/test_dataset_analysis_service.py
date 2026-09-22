from contextlib import AbstractContextManager
from datetime import date
from decimal import Decimal

import pytest

from sales_forecast.database.models import AnalysisRun, Dataset, SalesRecord
from sales_forecast.repositories.datasets import DatasetNotFoundError
from sales_forecast.services.dataset_analysis import DatasetAnalysisService, SAFE_ANALYSIS_FAILURE


class _Transaction(AbstractContextManager):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeSession(AbstractContextManager):
    def begin(self):
        return _Transaction()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeDatasets:
    def __init__(self, records: list[SalesRecord] | None = None, exists: bool = True) -> None:
        self.records = records if records is not None else []
        self.exists = exists
        self.dataset = Dataset(id=9, name="Fixture", original_filename="fixture.csv", rows_count=len(self.records))

    def get_by_id(self, session, dataset_id: int):
        if not self.exists:
            raise DatasetNotFoundError(dataset_id)
        return self.dataset

    def get_sales_records(self, session, dataset_id: int):
        return self.records


class FakeAnalysisRuns:
    def __init__(self) -> None:
        self.run = AnalysisRun(id=71, dataset_id=9, analysis_type="descriptive", status="running")

    def create_running(self, session, dataset_id: int):
        return self.run

    def complete(self, session, run_id: int, result_json):
        self.run.status = "completed"
        self.run.result_json = result_json
        return self.run

    def fail(self, session, run_id: int, message: str):
        self.run.status = "failed"
        self.run.error_message = message


def _record() -> SalesRecord:
    return SalesRecord(
        dataset_id=9, date=date(2025, 1, 1), product="Product", category="Category", units_sold=2,
        revenue=Decimal("20"), price=Decimal("10"), discount_pct=Decimal("0"), ad_spend=Decimal("1"), promo=False,
    )


def test_nonexistent_dataset_is_clear_error() -> None:
    service = DatasetAnalysisService(lambda: FakeSession(), datasets=FakeDatasets(exists=False), analysis_runs=FakeAnalysisRuns())
    with pytest.raises(DatasetNotFoundError):
        service.analyze(404)


def test_successful_analysis_completes_and_persists_json_result() -> None:
    runs = FakeAnalysisRuns()
    service = DatasetAnalysisService(lambda: FakeSession(), datasets=FakeDatasets([_record()]), analysis_runs=runs)

    execution = service.analyze(9)

    assert execution.analysis_run_id == 71
    assert runs.run.status == "completed"
    assert runs.run.result_json["kpis"]["total_revenue"] == 20.0


def test_failure_marks_existing_analysis_run_as_failed() -> None:
    runs = FakeAnalysisRuns()
    service = DatasetAnalysisService(lambda: FakeSession(), datasets=FakeDatasets([]), analysis_runs=runs)

    with pytest.raises(ValueError, match="contains no sales records"):
        service.analyze(9)

    assert runs.run.status == "failed"
    assert runs.run.error_message == SAFE_ANALYSIS_FAILURE
