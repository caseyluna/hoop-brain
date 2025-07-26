# api/Dockerfile

FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Set envs
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

RUN uv sync

# Copy code
COPY ./app ./app

COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

# Expose FastAPI port
EXPOSE 8000

# Start app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
