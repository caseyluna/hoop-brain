FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

WORKDIR /app
COPY . /app

ENV PATH="/app/.venv/bin:$PATH"

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync
