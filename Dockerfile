FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY demo_data ./demo_data
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic

CMD ["python", "-m", "sales_forecast.scripts.smoke_check"]
