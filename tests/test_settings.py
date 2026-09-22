from sales_forecast.config.settings import Settings


def test_settings_loads_required_and_optional_values() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:password@localhost:5432/database",
        log_level="DEBUG",
        openai_model="reserved-model",
    )

    assert settings.log_level == "DEBUG"
    assert settings.openai_model == "reserved-model"
    assert settings.openai_api_key is None
