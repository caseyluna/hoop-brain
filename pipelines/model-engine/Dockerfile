ARG CACHEBUSTER
FROM python:3.13-slim
RUN echo "Cachebuster: $CACHEBUSTER"
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

COPY . /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
