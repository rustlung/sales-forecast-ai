# Database: M2 import schema

The PostgreSQL schema stores uploaded dataset metadata, imported raw sales records, and future analytical results. Timestamps use `TIMESTAMP WITH TIME ZONE`; PostgreSQL `now()` is their server default. M2 does not change the M1 schema or require a new migration.

`datasets` is deliberately protected by `ON DELETE RESTRICT` from all child tables. A dataset is the audit anchor for imported source data and derived results, so its removal must first be explicit and controlled; M1 does not cascade-delete sales history, analyses, or forecasts.

## Tables

### `datasets`

Purpose: metadata and coverage of one uploaded sales dataset.

| Field | Type | Key / constraints |
| --- | --- | --- |
| `id` | `integer` | PK |
| `name` | `varchar(255)` | required |
| `original_filename` | `varchar(512)` | required |
| `uploaded_at` | `timestamptz` | required, defaults to `now()` |
| `date_from` | `date` | nullable |
| `date_to` | `date` | nullable; must be no earlier than `date_from` |
| `rows_count` | `integer` | required, defaults to 0, non-negative |

Index: `ix_datasets_uploaded_at (uploaded_at)`.

### `sales_records`

Purpose: imported source rows for a dataset. M2 validates each CSV entirely before opening the write transaction, then creates the dataset and bulk-inserts its rows in one transaction.

| Field | Type | Key / constraints |
| --- | --- | --- |
| `id` | `integer` | PK |
| `dataset_id` | `integer` | FK → `datasets.id`, required, `ON DELETE RESTRICT` |
| `date` | `date` | required |
| `product` | `varchar(255)` | required |
| `category` | `varchar(255)` | required |
| `units_sold` | `integer` | required, ≥ 0 |
| `revenue` | `numeric(14,2)` | required, ≥ 0 |
| `price` | `numeric(14,2)` | required, ≥ 0 |
| `discount_pct` | `numeric(5,2)` | required, defaults to 0, 0–100 |
| `ad_spend` | `numeric(14,2)` | required, defaults to 0, ≥ 0 |
| `promo` | `boolean` | required, defaults to `false` |

Indexes: `ix_sales_records_dataset_date (dataset_id, date)`, `ix_sales_records_product (product)`, `ix_sales_records_category (category)`.

### `analysis_runs`

Purpose: execution metadata and future result/error payload of a historical analysis.

| Field | Type | Key / constraints |
| --- | --- | --- |
| `id` | `integer` | PK |
| `dataset_id` | `integer` | FK → `datasets.id`, required, `ON DELETE RESTRICT` |
| `created_at` | `timestamptz` | required, defaults to `now()` |
| `analysis_type` | `varchar(100)` | required |
| `status` | `varchar(50)` | required |
| `result_json` | `jsonb` | nullable |
| `error_message` | `text` | nullable |

Indexes: `ix_analysis_runs_dataset_created_at (dataset_id, created_at)`, `ix_analysis_runs_status (status)`.

### `forecasts`

Purpose: metadata and JSON results of a future forecast run.

| Field | Type | Key / constraints |
| --- | --- | --- |
| `id` | `integer` | PK |
| `dataset_id` | `integer` | FK → `datasets.id`, required, `ON DELETE RESTRICT` |
| `created_at` | `timestamptz` | required, defaults to `now()` |
| `target` | `varchar(100)` | required |
| `model_name` | `varchar(100)` | required |
| `horizon_days` | `integer` | required, > 0 |
| `metrics_json` | `jsonb` | required |
| `forecast_json` | `jsonb` | required |

Indexes: `ix_forecasts_dataset_created_at (dataset_id, created_at)`, `ix_forecasts_target (target)`.

## Relationships

```text
datasets (1) ──< sales_records
     │
     ├────< analysis_runs
     │
     └────< forecasts
```

Each child belongs to exactly one dataset. The foreign keys use `RESTRICT`, so a `datasets` row cannot be deleted while any child row remains.

## Diagnostic SQL

Run these with `psql` connected to the target database.

```sql
-- List application tables.
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Describe a table in psql (meta-command, not SQL).
\d+ sales_records

-- Recently uploaded datasets.
SELECT id, name, original_filename, uploaded_at, date_from, date_to, rows_count
FROM datasets
ORDER BY uploaded_at DESC
LIMIT 20;

-- First records in one imported dataset. Replace :dataset_id in your client.
SELECT id, date, product, category, units_sold, revenue, price, discount_pct, ad_spend, promo
FROM sales_records
WHERE dataset_id = :dataset_id
ORDER BY date ASC, id ASC
LIMIT 20;

-- Last records in one imported dataset.
SELECT id, date, product, category, units_sold, revenue
FROM sales_records
WHERE dataset_id = :dataset_id
ORDER BY date DESC, id DESC
LIMIT 20;

-- Count source rows for one dataset. Replace :dataset_id in your SQL client.
SELECT dataset_id, COUNT(*) AS sales_records_count
FROM sales_records
WHERE dataset_id = :dataset_id
GROUP BY dataset_id;

-- Persisted date range and metadata for one dataset.
SELECT id, name, date_from, date_to, rows_count
FROM datasets
WHERE id = :dataset_id;

-- Aggregate revenue for one dataset.
SELECT dataset_id, SUM(revenue) AS total_revenue
FROM sales_records
WHERE dataset_id = :dataset_id
GROUP BY dataset_id;

-- Record counts by product and category.
SELECT category, product, COUNT(*) AS records_count
FROM sales_records
WHERE dataset_id = :dataset_id
GROUP BY category, product
ORDER BY category, product;

-- Latest analysis attempts.
SELECT id, dataset_id, created_at, analysis_type, status, error_message
FROM analysis_runs
ORDER BY created_at DESC
LIMIT 20;

-- Safe pre-delete check: inspect the dataset and dependent row counts first.
SELECT d.id, d.name,
       COUNT(DISTINCT sr.id) AS sales_records_count,
       COUNT(DISTINCT ar.id) AS analysis_runs_count,
       COUNT(DISTINCT f.id) AS forecasts_count
FROM datasets d
LEFT JOIN sales_records sr ON sr.dataset_id = d.id
LEFT JOIN analysis_runs ar ON ar.dataset_id = d.id
LEFT JOIN forecasts f ON f.dataset_id = d.id
WHERE d.id = :dataset_id
GROUP BY d.id, d.name;

-- Delete only an empty test dataset after the preceding check returns zero children.
DELETE FROM datasets
WHERE id = :dataset_id;
```

The final `DELETE` fails if related rows exist, by design. To remove a test dataset with child rows, first explicitly delete the children in a transaction after reviewing them, then delete the dataset; that process is intentionally not automated in M1.
