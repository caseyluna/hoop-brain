# use python 3.13-slim as the base image
FROM python:3.13-slim

# install uv
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:/app/src"

WORKDIR /app

# copy dependency files
COPY pyproject.toml uv.lock* ./

# copy src code
COPY src/ ./src/
COPY tests/ ./tests/

# install dependencies
RUN uv sync
