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

Use the existing local `.env` and adjust `DATABASE_URL` only if you run PostgreSQL outside Docker. Do not overwrite an existing `.env`.

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

### Russian demo profile

The default demo file remains unchanged. A second reproducible profile creates 365 days of fully synthetic Russian-language home-goods data (six products, four categories, 2,190 rows):

```powershell
python -m sales_forecast.scripts.generate_demo_data --profile ru
docker compose run --rm --no-deps app python -m sales_forecast.scripts.import_csv demo_data/sales_demo_ru.csv --name "Демо-продажи — товары для дома"
```

The RU profile has its own fixed seed and a different demand pattern. Use the import command once for the integration dataset; it remains a separate dataset from the original demo data.

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

## M3 descriptive analytics

M3 reads one imported dataset and produces deterministic descriptive analytics: KPI, daily/weekly/monthly series, product/category breakdowns, weekday and monthly seasonality, rankings, trend indicators, and Pearson correlations. It does not forecast future values.

```powershell
docker compose run --rm --no-deps app python -m sales_forecast.scripts.analyze_dataset 1
```

Example summary:

```text
analysis_run_id=1 total_revenue=123456.78 units_sold=12345 date_from=2024-01-01 date_to=2024-12-30 products=5 categories=3
```

The full structured result is stored in `analysis_runs.result_json`. To additionally write it to a local file from a local Python environment, use `--output-json analysis.json`.

Pearson correlation is descriptive only: it measures co-movement in the imported records and does not establish causation.

## M4 forecasting

M4 compares two daily time-series models for `revenue` (default) or `units_sold`: a weekly Seasonal Naive baseline and Prophet. The final validation tail is held out from training; random splitting is not used because it would leak future observations into a time-series training set.

Metrics are MAE, RMSE and MAPE. MAPE excludes zero actuals and falls back to MAE for model selection when more than half of validation actuals are zero. The lower MAPE otherwise selects the model; the selected model is refit on all available history before forecasting.

```powershell
docker compose run --rm --no-deps app python -m sales_forecast.scripts.forecast_dataset 1 --target revenue --horizon 30
```

Forecasting requires at least 90 continuous calendar days. Missing dates are rejected rather than silently filled: import an explicit zero-sales date only when it is valid for the source data. Forecast values are clipped at zero; Prophet intervals are retained, while Seasonal Naive intentionally has no artificial confidence interval.

A forecast is a statistical estimate, not a guarantee of future sales or revenue.

## M5 scenario modeling

Scenario modeling uses `RandomForestRegressor` to estimate revenue for one product/date row from price, discount, ad spend, promo, weekday, month, product and category. It is distinct from time-series forecasting: it evaluates a supplied factor combination rather than extending a future series. Training/test data are split chronologically by whole dates. Feature importance and scenario results do not establish causation.

```powershell
python -m sales_forecast.scripts.run_scenario 1 --product "Wireless Headphones" --category "Electronics" --date 2025-01-15 --price 79.99 --discount 10 --ad-spend 150 --promo true
```

## M6 AI insights

Python and ML calculate all metrics; the LLM only interprets compact saved results through ProxyAPI. The request uses strict JSON Schema Structured Outputs derived from the `AIInsights` Pydantic model; `scenario_commentary` is nullable when no saved scenario exists. It requires `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` in the existing `.env`.

```powershell
python -m sales_forecast.scripts.generate_ai_insights 1 --target revenue
```

AI output is constrained to supplied data and does not replace business analysis.

## M7 Dashboard

Streamlit is a presentation layer over the existing repositories and services: it does not calculate KPI, train models, or call the OpenAI SDK directly. Heavy operations run only after a corresponding button is pressed.

The dashboard has five Russian-language tabs:

- **Обзор** — KPI cards and daily revenue;
- **Аналитика** — product/category breakdowns, seasonality and correlations;
- **Прогноз** — saved or explicitly requested Prophet / Seasonal Naive forecast;
- **Сценарии** — saved or explicitly requested Random Forest scenario;
- **AI-инсайты** — saved or explicitly requested ProxyAPI interpretation.

For a local development environment with a reachable `DATABASE_URL` in the existing `.env`:

```powershell
streamlit run src/sales_forecast/ui/app.py
```

For Docker, build the application image and start the dashboard with PostgreSQL:

```powershell
docker compose build app
docker compose up -d --wait postgres dashboard
```

Open [http://localhost:8501](http://localhost:8501). The existing `.env` is used as-is; do not overwrite it. The dashboard reads existing datasets and never imports demo CSV automatically.

All visible numbers use Russian formatting (spaces for thousands and commas for decimals). The dashboard localizes weekdays, months, and sklearn feature names only for display; calculations and saved source results retain their canonical values. New AI-insights requests receive a compact, human-readable rounded payload, while saved analytics, forecasting, and scenario results remain unchanged.

## Tests

```powershell
pytest
```

See [database documentation](docs/database.md) for the initial schema and diagnostic SQL.
