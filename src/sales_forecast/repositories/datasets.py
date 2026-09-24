"""Focused persistence operations for imported sales datasets."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sales_forecast.database.models import Dataset, SalesRecord
from sales_forecast.services.csv_validation import NormalizedSalesRecord


class DatasetRepository:
    def list_all(self, session: Session) -> list[Dataset]:
        return list(session.scalars(select(Dataset).order_by(Dataset.uploaded_at.desc(), Dataset.id.desc())))

    def get_by_id(self, session: Session, dataset_id: int) -> Dataset:
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset

    def get_sales_records(self, session: Session, dataset_id: int) -> list[SalesRecord]:
        self.get_by_id(session, dataset_id)
        statement = select(SalesRecord).where(SalesRecord.dataset_id == dataset_id).order_by(SalesRecord.date, SalesRecord.id)
        return list(session.scalars(statement))

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


class DatasetNotFoundError(Exception):
    def __init__(self, dataset_id: int) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"Dataset with id {dataset_id} does not exist")
