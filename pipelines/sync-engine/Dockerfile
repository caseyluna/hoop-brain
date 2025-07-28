# infra/dagger/Dockerfile.dev  (or wherever you reference it)

# 1) Start from a slim Python image
FROM python:3.13-slim

# 2) Pull in the `uv` binary for dependency management
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

# 3) Configure UV and PATH
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

# 4) Set working directory
WORKDIR /app

# 5) Copy only your dependency files and install them
COPY pyproject.toml uv.lock* ./
RUN uv sync

# 6) Copy the rest of your code
COPY src/ src/
COPY tests/ tests/

# 7) (Optional) Expose ports or set entrypoint if you like,
#    but for Dagger you typically just run commands via `.with_exec()`
