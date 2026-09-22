"""Create initial sales forecast schema.

Revision ID: 20260922_0001
Revises:
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260922_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("rows_count", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("rows_count >= 0", name="ck_datasets_rows_count_nonnegative"),
        sa.CheckConstraint("date_to IS NULL OR date_from IS NULL OR date_to >= date_from", name="ck_datasets_date_range"),
    )
    op.create_index("ix_datasets_uploaded_at", "datasets", ["uploaded_at"])

    op.create_table(
        "sales_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("product", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.Column("units_sold", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount_pct", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False),
        sa.Column("ad_spend", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False),
        sa.Column("promo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("units_sold >= 0", name="ck_sales_records_units_sold_nonnegative"),
        sa.CheckConstraint("revenue >= 0", name="ck_sales_records_revenue_nonnegative"),
        sa.CheckConstraint("price >= 0", name="ck_sales_records_price_nonnegative"),
        sa.CheckConstraint("discount_pct >= 0 AND discount_pct <= 100", name="ck_sales_records_discount_pct_range"),
        sa.CheckConstraint("ad_spend >= 0", name="ck_sales_records_ad_spend_nonnegative"),
    )
    op.create_index("ix_sales_records_dataset_date", "sales_records", ["dataset_id", "date"])
    op.create_index("ix_sales_records_product", "sales_records", ["product"])
    op.create_index("ix_sales_records_category", "sales_records", ["category"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("analysis_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_analysis_runs_dataset_created_at", "analysis_runs", ["dataset_id", "created_at"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("target", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("forecast_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("horizon_days > 0", name="ck_forecasts_horizon_days_positive"),
    )
    op.create_index("ix_forecasts_dataset_created_at", "forecasts", ["dataset_id", "created_at"])
    op.create_index("ix_forecasts_target", "forecasts", ["target"])


def downgrade() -> None:
    op.drop_table("forecasts")
    op.drop_table("analysis_runs")
    op.drop_table("sales_records")
    op.drop_table("datasets")
