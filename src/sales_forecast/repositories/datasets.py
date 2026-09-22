"""Focused persistence operations for imported sales datasets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import insert
from sqlalchemy.orm import Session

from sales_forecast.database.models import Dataset, SalesRecord
from sales_forecast.services.csv_validation import NormalizedSalesRecord


class DatasetRepository:
    def create_with_sales_records(
        self,
        session: Session,
        *,
        name: str,
        original_filename: str,
        date_from: date,
        date_to: date,
        records: Sequence[NormalizedSalesRecord],
    ) -> Dataset:
        dataset = Dataset(
            name=name,
            original_filename=original_filename,
            date_from=date_from,
            date_to=date_to,
            rows_count=len(records),
        )
        session.add(dataset)
        session.flush()
        session.execute(insert(SalesRecord), [record.as_insert_mapping(dataset.id) for record in records])
        return dataset
