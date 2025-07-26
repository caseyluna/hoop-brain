# use slim python base image
FROM python:3.11-slim

# install uv
COPY --from=ghcr.io/astral-sh/uv:0.4.9 /uv /bin/uv

# set workdir
WORKDIR /app

# copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# copy code
COPY . /app

ENV PATH="/app/.venv/bin:$PATH"

# install deps with uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# expose port for FASTAPI
EXPOSE 8000

# default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
