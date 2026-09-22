# Sales Forecast AI

Infrastructure foundation for an AI system that will analyse historical sales, forecast outcomes, compare models, model scenarios, and provide AI insights. This M1 milestone intentionally contains no CSV import, analytics, ML/Prophet, OpenAI integration, or Streamlit UI.

## Stack

- Python 3.12
- PostgreSQL 16
- SQLAlchemy 2.x (synchronous)
- Alembic
- Pydantic Settings
- Docker Compose and pytest

## Local setup

Create a local environment file from the example and adjust `DATABASE_URL` if you run PostgreSQL outside Docker:

```powershell
Copy-Item .env.example .env
```

Install development dependencies locally:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Docker and migrations

Start PostgreSQL and wait for its healthcheck:

```powershell
docker compose up -d --build postgres
docker compose up -d --wait postgres
```

Run the initial migration and infrastructure check inside the application image:

```powershell
docker compose run --rm --no-deps app alembic upgrade head
docker compose run --rm --no-deps app python -m sales_forecast.scripts.smoke_check
```

The `.env.example` database hostname is `postgres`, so it is intended for commands run in Docker. For a local host-based command, set `DATABASE_URL` in `.env` to a reachable host PostgreSQL address.

## Tests

```powershell
pytest
```

See [database documentation](docs/database.md) for the initial schema and diagnostic SQL.
