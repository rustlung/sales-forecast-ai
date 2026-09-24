from pathlib import Path

import pytest

from sales_forecast.services.csv_validation import CsvIssue, CsvValidationError
from sales_forecast.services.dataset_import import ImportResult
from sales_forecast.ui.uploads import (
    import_uploaded_csv,
    resolve_dataset_name,
    validation_error_message,
)


class FakeUpload:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


class FakeImportService:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.name: str | None = None

    def import_csv(self, path: Path, name: str | None = None) -> ImportResult:
        self.path = path
        self.name = name
        assert path.read_bytes().startswith(b"date,")
        return ImportResult(15, 2, "2025-01-01", "2025-01-02")


def test_uploaded_file_uses_service_and_removes_temporary_file() -> None:
    service = FakeImportService()
    summary = import_uploaded_csv(FakeUpload("branch_sales.csv", b"date,product\n"), " Продажи филиала ", service)  # type: ignore[arg-type]

    assert service.name == "Продажи филиала"
    assert service.path is not None and not service.path.exists()
    assert summary.dataset_id == 15
    assert "Продажи филиала" in summary.success_message()
    assert "01.01.2025 — 02.01.2025" in summary.success_message()


def test_empty_name_falls_back_to_filename() -> None:
    assert resolve_dataset_name("   ", "branch_sales.csv") == "branch sales"


def test_validation_error_is_safe_and_russian() -> None:
    error = CsvValidationError([CsvIssue(17, "discount_pct", "must be at most 100")])
    assert validation_error_message(error) == "Ошибка в строке 17, поле «discount_pct»: значение должно быть не больше 100."
