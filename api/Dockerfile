# Use python 3.13-slim as the base image
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv
RUN apt-get update && \
  apt-get install -y \
  postgresql-client \
  bash \
  && rm -rf /var/lib/apt/lists/*

# Set environment variables for uv and ensure .venv/bin is in PATH
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# Copy dependency files first for better Docker cache usage
COPY pyproject.toml uv.lock* ./

# Install dependencies into .venv
RUN uv sync

# Copy the rest of the code
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini
COPY ./tests ./tests
COPY ./scripts ./scripts


EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
