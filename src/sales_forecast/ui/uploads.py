"""Temporary-file adapter between Streamlit uploads and the existing import service."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Iterator, Protocol

from sales_forecast.services.csv_validation import CsvValidationError
from sales_forecast.services.dataset_import import DatasetImportService, ImportResult


class UploadedCsv(Protocol):
    name: str

    def getvalue(self) -> bytes: ...


@dataclass(frozen=True)
class ImportPresentation:
    dataset_id: int
    name: str
    rows_count: int
    date_from: str
    date_to: str

    def success_message(self) -> str:
        return f"Датасет «{self.name}» успешно импортирован: {self.rows_count:,} строк, период {_display_date(self.date_from)} — {_display_date(self.date_to)}.".replace(",", " ")


def import_uploaded_csv(upload: UploadedCsv, name: str | None, service: DatasetImportService) -> ImportPresentation:
    dataset_name = resolve_dataset_name(name, upload.name)
    with temporary_uploaded_csv(upload) as path:
        result = service.import_csv(path, dataset_name)
    return presentation_from_result(result, dataset_name)


def resolve_dataset_name(name: str | None, filename: str) -> str:
    return name.strip() if name and name.strip() else Path(filename).stem.replace("_", " ")


def presentation_from_result(result: ImportResult, name: str) -> ImportPresentation:
    return ImportPresentation(result.dataset_id, name, result.rows_count, result.date_from, result.date_to)


def validation_error_message(error: CsvValidationError) -> str:
    if not error.issues:
        return "CSV не прошёл проверку."
    issue = error.issues[0]
    location = f"в строке {issue.row_number}" if issue.row_number is not None else "в заголовке"
    return f"Ошибка {location}, поле «{issue.field}»: {_russian_reason(issue.reason)}."


@contextmanager
def temporary_uploaded_csv(upload: UploadedCsv) -> Iterator[Path]:
    suffix = Path(upload.name).suffix.lower() or ".csv"
    with NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(upload.getvalue())
        path = Path(temporary_file.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _russian_reason(reason: str) -> str:
    translations = {
        "required column is missing": "отсутствует обязательная колонка",
        "value is required": "значение обязательно",
        "expected ISO date YYYY-MM-DD": "ожидается дата в формате YYYY-MM-DD",
        "expected a decimal number": "ожидается число",
        "must be greater than 0": "значение должно быть больше 0",
        "must be at least 0": "значение должно быть не меньше 0",
        "must be at most 100": "значение должно быть не больше 100",
        "must be an integer": "ожидается целое число",
    }
    return translations.get(reason, reason)


def _display_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value
