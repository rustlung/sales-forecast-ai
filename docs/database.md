# База данных

Sales Forecast AI использует PostgreSQL и SQLAlchemy 2.x. Схема создаётся и изменяется только через Alembic. Все timestamps хранятся как timezone-aware значения (`TIMESTAMP WITH TIME ZONE`).

## Схема связей

```text
datasets
 ├─< sales_records
 ├─< analysis_runs
 └─< forecasts
```

`datasets` — корневая сущность загруженного CSV. Каждая запись продаж, запуск аналитики и прогноз привязаны к одному датасету.

## Политика удаления

Внешние ключи зависимых таблиц используют `ON DELETE RESTRICT`. Удаление датасета намеренно не происходит каскадно: оно могло бы незаметно удалить историю продаж, результаты аналитики и прогнозы. Перед удалением необходимо удалить зависимые записи явно либо использовать полный reset только в локальном/demo окружении.

## Таблицы

### `datasets`

Метаданные одного импорта CSV.

| Поле | Тип | Ключ / ограничение | Назначение |
| --- | --- | --- | --- |
| `id` | `BIGINT` | PK | Идентификатор датасета. |
| `name` | `VARCHAR(255)` | NOT NULL | Отображаемое имя датасета. |
| `original_filename` | `VARCHAR(512)` | NOT NULL | Исходное имя загруженного файла. |
| `uploaded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL | Время успешного импорта. |
| `date_from` | `DATE` | nullable | Минимальная дата продаж. |
| `date_to` | `DATE` | nullable, `date_from <= date_to` при наличии обеих дат | Максимальная дата продаж. |
| `rows_count` | `INTEGER` | NOT NULL, `rows_count >= 0` | Число импортированных строк. |

Индекс: по `uploaded_at`.

### `sales_records`

Нормализованные исторические записи. Одна строка описывает продажи одного товара за одну дату в импортированном наборе.

| Поле | Тип | Ключ / ограничение | Назначение |
| --- | --- | --- | --- |
| `id` | `BIGINT` | PK | Идентификатор записи. |
| `dataset_id` | `INTEGER` | FK → `datasets.id`, NOT NULL, RESTRICT | Родительский датасет. |
| `date` | `DATE` | NOT NULL | Дата наблюдения. |
| `product` | `VARCHAR(255)` | NOT NULL | Товар. |
| `category` | `VARCHAR(255)` | NOT NULL | Категория. |
| `units_sold` | `INTEGER` | NOT NULL, `>= 0` | Продажи, шт. |
| `revenue` | `NUMERIC(14, 2)` | NOT NULL, `>= 0` | Выручка. |
| `price` | `NUMERIC(14, 2)` | NOT NULL, `>= 0` | Цена. |
| `discount_pct` | `NUMERIC(5, 2)` | NOT NULL, `0..100` | Скидка, %. |
| `ad_spend` | `NUMERIC(14, 2)` | NOT NULL, `>= 0` | Рекламные расходы. |
| `promo` | `BOOLEAN` | NOT NULL | Промо-признак. |

Индексы: составной `(dataset_id, date)`, а также отдельные по `product` и `category`.

### `analysis_runs`

Журнал запусков описательной аналитики, сценарного моделирования и AI-инсайтов.

| Поле | Тип | Ключ / ограничение | Назначение |
| --- | --- | --- | --- |
| `id` | `BIGINT` | PK | Идентификатор запуска. |
| `dataset_id` | `INTEGER` | FK → `datasets.id`, NOT NULL, RESTRICT | Анализируемый датасет. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL | Время создания запуска. |
| `analysis_type` | `VARCHAR(100)` | NOT NULL | Тип: `descriptive`, `scenario` или `ai_insights`. |
| `status` | `VARCHAR(50)` | NOT NULL | Жизненный цикл: `running`, `completed`, `failed`. |
| `result_json` | `JSONB` | nullable | JSON-safe результат завершённого запуска. |
| `error_message` | `TEXT` | nullable | Безопасное сообщение об ошибке для failed запуска. |

Индексы: составной `(dataset_id, created_at)` и отдельный по `status`.

`result_json` хранит разные структуры в зависимости от `analysis_type`: KPI и временные ряды для `descriptive`, метрики/baseline/сценарий для `scenario`, а для `ai_insights` — compact payload, `model_name` и валидированный `ai_result`. Поле не предназначено для хранения секретов или raw API response.

### `forecasts`

Сохранённые результаты forecasting service.

| Поле | Тип | Ключ / ограничение | Назначение |
| --- | --- | --- | --- |
| `id` | `BIGINT` | PK | Идентификатор прогноза. |
| `dataset_id` | `INTEGER` | FK → `datasets.id`, NOT NULL, RESTRICT | Исходный датасет. |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL | Время расчёта. |
| `target` | `VARCHAR(100)` | NOT NULL | `revenue` или `units_sold`. |
| `model_name` | `VARCHAR(100)` | NOT NULL | Выбранная модель: Prophet или Seasonal Naive. |
| `horizon_days` | `INTEGER` | NOT NULL, `> 0` | Горизонт в днях. |
| `metrics_json` | `JSONB` | NOT NULL | Метрики обеих моделей и данные validation. |
| `forecast_json` | `JSONB` | NOT NULL | История, параметры выбора и future forecast points. |

Индексы: составной `(dataset_id, created_at)` и отдельный по `target`.

## SQL для диагностики

Все примеры предназначены для `psql`. Подставляйте конкретный идентификатор вместо `:dataset_id` или используйте параметр вашего SQL-клиента.

### Список таблиц

```sql
\dt
```

### Описание таблицы

```sql
\d+ datasets
\d+ sales_records
\d+ analysis_runs
\d+ forecasts
```

### Последние импортированные датасеты

```sql
SELECT id, name, original_filename, uploaded_at, date_from, date_to, rows_count
FROM datasets
ORDER BY uploaded_at DESC, id DESC
LIMIT 20;
```

### Количество и диапазон записей датасета

```sql
SELECT
    d.id,
    d.name,
    d.rows_count AS declared_rows_count,
    COUNT(sr.id) AS actual_sales_records,
    MIN(sr.date) AS actual_date_from,
    MAX(sr.date) AS actual_date_to
FROM datasets AS d
LEFT JOIN sales_records AS sr ON sr.dataset_id = d.id
WHERE d.id = :dataset_id
GROUP BY d.id, d.name, d.rows_count;
```

### Первые и последние записи продаж

```sql
SELECT date, product, category, units_sold, revenue, price, discount_pct, ad_spend, promo
FROM sales_records
WHERE dataset_id = :dataset_id
ORDER BY date ASC, product ASC
LIMIT 20;

SELECT date, product, category, units_sold, revenue
FROM sales_records
WHERE dataset_id = :dataset_id
ORDER BY date DESC, product ASC
LIMIT 20;
```

### Выручка и количество строк по товару и категории

```sql
SELECT product, category, COUNT(*) AS records_count, SUM(revenue) AS total_revenue
FROM sales_records
WHERE dataset_id = :dataset_id
GROUP BY product, category
ORDER BY total_revenue DESC;
```

### Последние запуски аналитики

```sql
SELECT id, dataset_id, analysis_type, status, created_at, error_message
FROM analysis_runs
WHERE dataset_id = :dataset_id
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### Failed и running запуски

```sql
SELECT id, dataset_id, analysis_type, status, created_at, error_message
FROM analysis_runs
WHERE status IN ('failed', 'running')
ORDER BY created_at DESC, id DESC;
```

### Извлечение полей JSONB из descriptive, scenario и AI-insights

```sql
SELECT
    id,
    result_json #>> '{kpis,total_revenue}' AS total_revenue,
    result_json #>> '{kpis,total_units_sold}' AS total_units_sold
FROM analysis_runs
WHERE dataset_id = :dataset_id
  AND analysis_type = 'descriptive'
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 1;

SELECT
    id,
    result_json #>> '{metrics,mae}' AS mae,
    result_json #>> '{scenario_predicted_revenue}' AS scenario_revenue,
    result_json #>> '{baseline_predicted_revenue}' AS baseline_revenue
FROM analysis_runs
WHERE dataset_id = :dataset_id
  AND analysis_type = 'scenario'
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 1;

SELECT
    id,
    result_json #>> '{model_name}' AS model_name,
    result_json #>> '{ai_result,summary}' AS summary
FROM analysis_runs
WHERE dataset_id = :dataset_id
  AND analysis_type = 'ai_insights'
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 1;
```

### Последние forecasts и конкретная метрика

```sql
SELECT id, dataset_id, target, model_name, horizon_days, created_at
FROM forecasts
ORDER BY created_at DESC, id DESC
LIMIT 20;

SELECT
    id,
    target,
    model_name,
    metrics_json #>> '{model_comparison,prophet,mape}' AS prophet_mape,
    metrics_json #>> '{model_comparison,seasonal_naive,mape}' AS seasonal_naive_mape
FROM forecasts
WHERE dataset_id = :dataset_id
ORDER BY created_at DESC
LIMIT 10;
```

### Первые точки сохранённого прогноза

```sql
SELECT
    id,
    target,
    model_name,
    jsonb_array_elements(forecast_json -> 'forecast_points') AS forecast_point
FROM forecasts
WHERE dataset_id = :dataset_id
ORDER BY created_at DESC
LIMIT 1;
```

## Безопасное удаление датасета

Сначала проверьте, какие зависимые данные существуют. Из-за `ON DELETE RESTRICT` простой `DELETE FROM datasets` при наличии зависимостей будет отклонён PostgreSQL.

```sql
SELECT
    d.id,
    d.name,
    COUNT(DISTINCT sr.id) AS sales_records,
    COUNT(DISTINCT ar.id) AS analysis_runs,
    COUNT(DISTINCT f.id) AS forecasts
FROM datasets AS d
LEFT JOIN sales_records AS sr ON sr.dataset_id = d.id
LEFT JOIN analysis_runs AS ar ON ar.dataset_id = d.id
LEFT JOIN forecasts AS f ON f.dataset_id = d.id
WHERE d.id = :dataset_id
GROUP BY d.id, d.name;
```

После проверки удаление одного тестового датасета выполняется осознанно и в транзакции:

```sql
BEGIN;

DELETE FROM forecasts WHERE dataset_id = :dataset_id;
DELETE FROM analysis_runs WHERE dataset_id = :dataset_id;
DELETE FROM sales_records WHERE dataset_id = :dataset_id;
DELETE FROM datasets WHERE id = :dataset_id;

COMMIT;
```

Этот порядок удаляет выбранный датасет и только его зависимые результаты. Замените `COMMIT` на `ROLLBACK`, если предварительная проверка выявила неверный идентификатор.

## Полная очистка пользовательских данных

Используйте только для локального/demo reset. Команда удаляет все датасеты, исторические записи и все производные результаты; схема и история Alembic сохраняются.

```sql
BEGIN;

TRUNCATE TABLE
    forecasts,
    analysis_runs,
    sales_records,
    datasets
RESTART IDENTITY;

SELECT 'datasets' AS table_name, COUNT(*) FROM datasets
UNION ALL
SELECT 'sales_records', COUNT(*) FROM sales_records
UNION ALL
SELECT 'analysis_runs', COUNT(*) FROM analysis_runs
UNION ALL
SELECT 'forecasts', COUNT(*) FROM forecasts;

COMMIT;
```

`alembic_version` не очищается, поэтому применённая schema остаётся на месте. Эта операция необратимо удаляет все пользовательские и demo-данные в текущей БД.
