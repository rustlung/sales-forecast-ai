# Sales Forecast AI

Foundation for an AI system that will analyse historical sales, forecast outcomes, compare models, model scenarios, and provide AI insights. M2 provides deterministic demo data and a PostgreSQL CSV import pipeline; analytics, forecasting, AI, and UI are still out of scope.

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

## Demo data and CSV import

Generate the reproducible synthetic demo file (five products, three categories, 365 daily observations, 1,825 rows):

```powershell
python -m sales_forecast.scripts.generate_demo_data
```

The file is written to `demo_data/sales_demo.csv`. To import it through the configured Docker PostgreSQL service:

```powershell
docker compose run --rm --no-deps app python -m sales_forecast.scripts.import_csv demo_data/sales_demo.csv --name "Demo sales dataset"
```

Expected output has this form:

```text
Imported dataset_id=1 rows_count=1825 date_from=2024-01-01 date_to=2024-12-30
```

Every import is an independent dataset; importing the same file twice is allowed and creates two separate `datasets` rows.

### Input format and validation

The CSV must be UTF-8, use a header row, and contain these required columns:

```text
date,product,category,units_sold,revenue,price,discount_pct,ad_spend,promo
```

- `date`: ISO `YYYY-MM-DD`.
- `product`, `category`: non-empty after trimming whitespace.
- `units_sold`: integer ≥ 0.
- `revenue`, `ad_spend`: finite decimal ≥ 0.
- `price`: finite decimal > 0.
- `discount_pct`: finite decimal from 0 through 100.
- `promo`: `true`/`false`, `1`/`0`, `yes`/`no`, or `y`/`n` (case-insensitive).

Fully empty rows are ignored. Missing values, invalid values, malformed rows, and invalid dates are reported with CSV row number, field, and reason; import then exits with code 2. Extra named columns are allowed and ignored, so source exports may include metadata outside the application schema.

Use `psql` or the diagnostic SQL in [database documentation](docs/database.md) to inspect imported rows.

## Tests

```powershell
pytest
```

See [database documentation](docs/database.md) for the initial schema and diagnostic SQL.
