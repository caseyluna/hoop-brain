# Adding New Features

How to extend Hoop Brain without hardcoding. Stick to the config-driven pattern so new entities and models slot in cleanly.

---

## 1. New Data Source (Ingestion → BQ → Mart → Sync)

When you want to pull in a new table from nba_api or elsewhere:

| Step | What to do |
|------|------------|
| 1. Ingest | Add `get_*()` and `ingest_*()` in `pipelines/ingestion-engine/src/modules/nba_api.py`. Call from `main.py`. Output: `nba-api/<table>.parquet` in GCS. |
| 2. Load | Extend `scripts/load_gcs_to_bq.py` (or add `--source`). Load parquet → `raw_nba_api.<table>`. |
| 3. Staging | Create `models/staging/stg_<table>.sql` in transformation-engine. Add source to `sources.yml`. Dedupe by primary key. |
| 4. Mart | Create `models/marts/<table>.sql` (or merge into existing mart). |
| 5. Sync | Add to `pipelines/sync-engine/src/config/sync_jobs.yaml`: `bq_view`, `pg_table`, `primary_key`. Extend allowlist in `bq_to_postgres.py`. |
| 6. Pipeline | Ensure `ingest-daily` (or relevant pipeline) runs load for the new table. |

**Files to touch:** ingestion-engine, load script, dbt models, sync_jobs.yaml.

---

## 2. New Model (Analytics in model-engine)

For things like RAPM, BPM, surplus value—anything that reads from marts and writes derived output:

| Step | What to do |
|------|------------|
| 1. Module | Add `pipelines/model-engine/src/models/<name>.py`. Read from BQ/Postgres (or parquet). |
| 2. Output | Write to a new BQ table or Postgres. Use a consistent naming pattern (e.g. `player_season_<metric>`). |
| 3. Pipeline | Add a job in `services.yaml` if needed. Wire into `pipelines.yaml` (e.g. run after dbt, before sync). |
| 4. Sync | If the output should be in Postgres for the API, add it to `sync_jobs.yaml`. |
| 5. API | Expose via a new endpoint if the frontend needs it. |

**Config keys:** `services.yaml`, `pipelines.yaml`, `sync_jobs.yaml`. Avoid hardcoding table names in the model.

---

## 3. New API Endpoint

| Step | What to do |
|------|------------|
| 1. Route | Create `api/app/api/routes/<module_name>.py` (e.g. `teams.py`). Define `@router.get("/")` or `@router.get("/{id}")` etc. |
| 2. Schema | Add `api/app/schemas/<module_name>.py` with Pydantic models. Use `from_attributes=True` for ORM. |
| 3. Model | If it's a new table, add `api/app/models/<module_name>.py` and an Alembic migration. |
| 4. Register | In `api/app/api/api_v1/api.py`: `from app.api.routes import <module_name>` then `router.include_router(<module_name>.router, prefix="/<resource>", tags=["<resource>"])` (e.g. module `teams` → prefix `/teams`). |
| 5. Test | Add `api/tests/test_<resource>.py`. Assert status and shape. |

---

## 4. New Frontend Page

| Step | What to do |
|------|------------|
| 1. Route | If using React Router, add a route (e.g. `/players/:id`). |
| 2. Component | Create the page component. Fetch from API (use relative URLs like `/api/v1/...` so the Vite proxy works). |
| 3. State | `useState` for data, `useEffect` for fetch. Handle loading and error. |
| 4. Nav | Add a link in the app shell if it should be discoverable. |

---

## Config Cheat Sheet

| Config | Purpose |
|--------|---------|
| `sync_jobs.yaml` | BQ view → Postgres table mapping. Add new rows for new entities. |
| `services.yaml` | Service definitions and jobs (lint, test, run-main). |
| `pipelines.yaml` | Pipeline steps. e.g. `ingest-daily` = ingest → load → dbt → sync. |
| `pipelines.yaml` (model-engine) | Add `model-<name>` pipeline if you have a new model job. |
