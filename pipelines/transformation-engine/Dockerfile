# pipelines/transformation-engine/Dockerfile
FROM python:3.13-slim

# 1) Bring in uv so `uv sync` works
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

# 2) Install DBT core plus Postgres & BigQuery adapters
RUN pip install dbt-core dbt-postgres dbt-bigquery

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# 3) Install Python deps
COPY pyproject.toml uv.lock* ./
RUN uv sync

# 4) Copy your *actual* DBT project
COPY dbt_project.yml ./
COPY models/ models/

# 5) (Optionally) other folders: macros/, data/, analyses/, etc.

# We leave profiles to Dagger to mount at runtime
CMD ["bash"]
