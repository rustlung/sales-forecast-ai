from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path

import pytest

from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.services.dataset_import import DatasetImportService


CSV_CONTENT = (
    "date,product,category,units_sold,revenue,price,discount_pct,ad_spend,promo\n"
    "2025-01-01,Product A,Category A,2,18.00,10.00,10,5,false\n"
    "2025-01-02,Product A,Category A,3,30.00,10.00,0,0,true\n"
)


class _Transaction(AbstractContextManager):
    def __init__(self, session: "FakeSession") -> None:
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.session.rolled_back = True
        else:
            self.session.committed = True
        return False


class FakeSession(AbstractContextManager):
    def __init__(self, fail_execute: bool = False) -> None:
        self.fail_execute = fail_execute
        self.dataset = None
        self.inserted_rows = []
        self.committed = False
        self.rolled_back = False

    def begin(self):
        return _Transaction(self)

    def add(self, dataset):
        self.dataset = dataset

    def flush(self):
        if self.dataset is not None and self.dataset.id is None:
            self.dataset.id = 41

    def execute(self, statement, rows):
        if self.fail_execute:
            raise RuntimeError("simulated persistence failure")
        self.inserted_rows.extend(rows)

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_successful_import_creates_dataset_and_all_sales_records(tmp_path) -> None:
    source = tmp_path / "input.csv"
    source.write_text(CSV_CONTENT, encoding="utf-8")
    session = FakeSession()
    service = DatasetImportService(lambda: session, DatasetRepository())

    result = service.import_csv(source, " Imported demo ")

    assert result.dataset_id == 41
    assert result.rows_count == 2
    assert result.date_from == "2025-01-01"
    assert result.date_to == "2025-01-02"
    assert session.dataset.name == "Imported demo"
    assert len(session.inserted_rows) == 2
    assert session.committed is True


def test_transaction_is_rolled_back_when_bulk_insert_fails(tmp_path) -> None:
    source = tmp_path / "input.csv"
    source.write_text(CSV_CONTENT, encoding="utf-8")
    session = FakeSession(fail_execute=True)
    service = DatasetImportService(lambda: session, DatasetRepository())

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        service.import_csv(source)

    assert session.rolled_back is True
    assert session.committed is False
