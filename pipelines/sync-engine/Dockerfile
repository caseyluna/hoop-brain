FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

WORKDIR /app
COPY . .

RUN uv sync
