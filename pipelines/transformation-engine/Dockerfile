FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

ENV PATH="/app/.venv/bin:$PATH" UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONPATH="/app"
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync

# Copy DBT project & profiles
COPY dbt_project.yml models/ profiles/ ./
