"""CSV validation and normalization for sales imports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


REQUIRED_COLUMNS = (
    "date",
    "product",
    "category",
    "units_sold",
    "revenue",
    "price",
    "discount_pct",
    "ad_spend",
    "promo",
)

TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}


@dataclass(frozen=True)
class CsvIssue:
    row_number: int | None
    field: str
    reason: str

    def __str__(self) -> str:
        location = f"row {self.row_number}" if self.row_number is not None else "header"
        return f"{location}, field '{self.field}': {self.reason}"


class CsvValidationError(Exception):
    """Expected, user-correctable CSV input errors."""

    def __init__(self, issues: list[CsvIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(str(issue) for issue in issues))


@dataclass(frozen=True)
class NormalizedSalesRecord:
    date: date
    product: str
    category: str
    units_sold: int
    revenue: Decimal
    price: Decimal
    discount_pct: Decimal
    ad_spend: Decimal
    promo: bool

    def as_insert_mapping(self, dataset_id: int) -> dict[str, object]:
        return {"dataset_id": dataset_id, **self.__dict__}


def read_and_validate_csv(path: Path) -> list[NormalizedSalesRecord]:
    """Read an UTF-8 CSV and return its canonical sales rows.

    Unknown columns are accepted and ignored so exports may carry descriptive
    metadata without widening the database contract.
    """
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            headers = reader.fieldnames
            if headers is None:
                raise CsvValidationError([CsvIssue(None, "CSV", "file has no header row")])
            missing = [column for column in REQUIRED_COLUMNS if column not in headers]
            if missing:
                raise CsvValidationError(
                    [CsvIssue(None, column, "required column is missing") for column in missing]
                )

            records: list[NormalizedSalesRecord] = []
            issues: list[CsvIssue] = []
            for row_number, raw_row in enumerate(reader, start=2):
                if _is_blank_row(raw_row):
                    continue
                extra_cells = raw_row.get(None)
                if extra_cells:
                    issues.append(CsvIssue(row_number, "CSV", "row has more values than the header"))
                    continue
                record, row_issues = _normalize_row(raw_row, row_number)
                issues.extend(row_issues)
                if record is not None:
                    records.append(record)
    except UnicodeDecodeError as error:
        raise CsvValidationError([CsvIssue(None, "CSV", "file must be UTF-8 encoded")]) from error

    if issues:
        raise CsvValidationError(issues)
    if not records:
        raise CsvValidationError([CsvIssue(None, "CSV", "file contains no data rows")])
    return records


def _is_blank_row(row: dict[str | None, str | None]) -> bool:
    return all(
        value is None
        or (isinstance(value, list) and all(not cell.strip() for cell in value))
        or (isinstance(value, str) and not value.strip())
        for value in row.values()
    )


def _normalize_row(
    row: dict[str | None, str | None], row_number: int
) -> tuple[NormalizedSalesRecord | None, list[CsvIssue]]:
    issues: list[CsvIssue] = []
    parsed_date = _parse_date(row, "date", row_number, issues)
    product = _parse_text(row, "product", row_number, issues)
    category = _parse_text(row, "category", row_number, issues)
    units_sold = _parse_integer(row, "units_sold", row_number, issues, minimum=0)
    revenue = _parse_decimal(row, "revenue", row_number, issues, minimum=Decimal("0"))
    price = _parse_decimal(row, "price", row_number, issues, minimum=Decimal("0"), strictly_positive=True)
    discount_pct = _parse_decimal(
        row, "discount_pct", row_number, issues, minimum=Decimal("0"), maximum=Decimal("100")
    )
    ad_spend = _parse_decimal(row, "ad_spend", row_number, issues, minimum=Decimal("0"))
    promo = _parse_boolean(row, "promo", row_number, issues)

    if issues:
        return None, issues
    assert all(value is not None for value in (parsed_date, product, category, units_sold, revenue, price, discount_pct, ad_spend, promo))
    return (
        NormalizedSalesRecord(
            date=parsed_date,
            product=product,
            category=category,
            units_sold=units_sold,
            revenue=revenue,
            price=price,
            discount_pct=discount_pct,
            ad_spend=ad_spend,
            promo=promo,
        ),
        [],
    )


def _value(row: dict[str | None, str | None], field: str, row_number: int, issues: list[CsvIssue]) -> str | None:
    value = row.get(field)
    if value is None or not value.strip():
        issues.append(CsvIssue(row_number, field, "value is required"))
        return None
    return value.strip()


def _parse_text(row: dict[str | None, str | None], field: str, row_number: int, issues: list[CsvIssue]) -> str | None:
    return _value(row, field, row_number, issues)


def _parse_date(row: dict[str | None, str | None], field: str, row_number: int, issues: list[CsvIssue]) -> date | None:
    value = _value(row, field, row_number, issues)
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        issues.append(CsvIssue(row_number, field, "expected ISO date YYYY-MM-DD"))
        return None


def _parse_decimal(
    row: dict[str | None, str | None],
    field: str,
    row_number: int,
    issues: list[CsvIssue],
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    strictly_positive: bool = False,
) -> Decimal | None:
    value = _value(row, field, row_number, issues)
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        issues.append(CsvIssue(row_number, field, "expected a decimal number"))
        return None
    if not number.is_finite():
        issues.append(CsvIssue(row_number, field, "must be a finite number"))
    elif strictly_positive and number <= 0:
        issues.append(CsvIssue(row_number, field, "must be greater than 0"))
    elif minimum is not None and number < minimum:
        issues.append(CsvIssue(row_number, field, f"must be at least {minimum}"))
    elif maximum is not None and number > maximum:
        issues.append(CsvIssue(row_number, field, f"must be at most {maximum}"))
    else:
        return number
    return None


def _parse_integer(
    row: dict[str | None, str | None], field: str, row_number: int, issues: list[CsvIssue], *, minimum: int
) -> int | None:
    number = _parse_decimal(row, field, row_number, issues, minimum=Decimal(minimum))
    if number is None:
        return None
    if number != number.to_integral_value():
        issues.append(CsvIssue(row_number, field, "must be an integer"))
        return None
    return int(number)


def _parse_boolean(row: dict[str | None, str | None], field: str, row_number: int, issues: list[CsvIssue]) -> bool | None:
    value = _value(row, field, row_number, issues)
    if value is None:
        return None
    lowered = value.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    issues.append(CsvIssue(row_number, field, "expected boolean: true/false, 1/0, yes/no, or y/n"))
    return None
