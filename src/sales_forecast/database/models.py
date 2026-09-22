from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint("rows_count >= 0", name="ck_datasets_rows_count_nonnegative"),
        CheckConstraint("date_to IS NULL OR date_from IS NULL OR date_to >= date_from", name="ck_datasets_date_range"),
        Index("ix_datasets_uploaded_at", "uploaded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    sales_records: Mapped[list[SalesRecord]] = relationship(back_populates="dataset")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="dataset")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="dataset")


class SalesRecord(Base):
    __tablename__ = "sales_records"
    __table_args__ = (
        CheckConstraint("units_sold >= 0", name="ck_sales_records_units_sold_nonnegative"),
        CheckConstraint("revenue >= 0", name="ck_sales_records_revenue_nonnegative"),
        CheckConstraint("price >= 0", name="ck_sales_records_price_nonnegative"),
        CheckConstraint("discount_pct >= 0 AND discount_pct <= 100", name="ck_sales_records_discount_pct_range"),
        CheckConstraint("ad_spend >= 0", name="ck_sales_records_ad_spend_nonnegative"),
        Index("ix_sales_records_dataset_date", "dataset_id", "date"),
        Index("ix_sales_records_product", "product"),
        Index("ix_sales_records_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    product: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    ad_spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    promo: Mapped[bool] = mapped_column(nullable=False, server_default="false")

    dataset: Mapped[Dataset] = relationship(back_populates="sales_records")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_dataset_created_at", "dataset_id", "created_at"),
        Index("ix_analysis_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped[Dataset] = relationship(back_populates="analysis_runs")


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        CheckConstraint("horizon_days > 0", name="ck_forecasts_horizon_days_positive"),
        Index("ix_forecasts_dataset_created_at", "dataset_id", "created_at"),
        Index("ix_forecasts_target", "target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    target: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    forecast_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="forecasts")
