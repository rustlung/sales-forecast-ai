"""Application service for atomic CSV imports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from sales_forecast.database.models import Dataset
from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.services.csv_validation import read_and_validate_csv


@dataclass(frozen=True)
class ImportResult:
    dataset_id: int
    rows_count: int
    date_from: str
    date_to: str


class DatasetImportService:
    def __init__(self, session_factory: sessionmaker[Session], repository: DatasetRepository | None = None) -> None:
        self._session_factory = session_factory
        self._repository = repository or DatasetRepository()

    def import_csv(self, csv_path: Path, name: str | None = None) -> ImportResult:
        records = read_and_validate_csv(csv_path)
        dataset_name = name.strip() if name and name.strip() else csv_path.stem.replace("_", " ")
        date_from = min(record.date for record in records)
        date_to = max(record.date for record in records)

        with self._session_factory() as session:
            with session.begin():
                dataset = self._repository.create_with_sales_records(
                    session,
                    name=dataset_name,
                    original_filename=csv_path.name,
                    date_from=date_from,
                    date_to=date_to,
                    records=records,
                )
                session.flush()
                result = _to_result(dataset)
        return result


def _to_result(dataset: Dataset) -> ImportResult:
    assert dataset.id is not None
    assert dataset.date_from is not None
    assert dataset.date_to is not None
    return ImportResult(
        dataset_id=dataset.id,
        rows_count=dataset.rows_count,
        date_from=dataset.date_from.isoformat(),
        date_to=dataset.date_to.isoformat(),
    )
