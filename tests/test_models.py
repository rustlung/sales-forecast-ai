from sales_forecast.database.models import AnalysisRun, Base, Dataset, Forecast, SalesRecord


def test_metadata_contains_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"datasets", "sales_records", "analysis_runs", "forecasts"}


def test_database_model_constraints_and_types() -> None:
    assert Dataset.__table__.c.uploaded_at.type.timezone is True
    assert AnalysisRun.__table__.c.result_json.type.__class__.__name__ == "JSONB"
    assert Forecast.__table__.c.metrics_json.type.__class__.__name__ == "JSONB"
    assert next(iter(SalesRecord.__table__.foreign_keys)).ondelete == "RESTRICT"
    assert "ix_sales_records_dataset_date" in {index.name for index in SalesRecord.__table__.indexes}
