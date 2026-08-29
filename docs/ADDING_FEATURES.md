# Adding New Features

How to extend Hoop Brain without hardcoding. Stick to the config-driven pattern so new entities and models slot in cleanly. Where a step isn't actually wired up yet, this doc says so and gives you the interim manual command — don't assume every arrow in the architecture diagram is a working pipeline today.

## Quick reference

| I want to...                                  | Go to |
|------------------------------------------------|-------|
| Pull in a new table/endpoint from nba_api or another source | §1 New Data Source |
| Build RAPM, traits, surplus value, or any other derived metric | §2 New Analytical Model |
| Add a table, or change fields on an existing one (Postgres) | §3 Postgres Schema Change |
| Expose something via `/api/v1/...` | §4 New/Updated API Endpoint |
| Add a screen to the web app | §5 New Frontend Page |

---

## 1. New Data Source (Ingestion → BQ → Mart → Sync)

When you want to pull in a new table from nba_api or elsewhere:

| Step | What to do |
|------|------------|
| 1. Ingest | Add `get_*()` and `ingest_*()` in `pipelines/ingestion-engine/src/modules/nba_api.py` (or a new module for a new source). Call from `main.py`. Output: `nba-api/<table>.parquet` in GCS via `upload_bytes_to_gcs` (see `core/storage_utils.py`). |
| 2. Load into BQ | **Gap today:** there's no repo script for this — load manually with the `bq` CLI until one exists: `bq load --source_format=PARQUET raw_nba_api.<table> gs://hoop-brain-raw-data/nba-api/<table>.parquet`. Creating a real load step (`ingestion-engine` job or standalone script) is worthwhile future ticket-sized work, not something to invent ad hoc mid-feature. |
| 3. Staging | Create `models/staging/stg_<table>.sql` in transformation-engine. Add the source to `sources.yml`. Dedupe by primary key. Add the uniqueness/not-null schema tests on that key (see CLAUDE.md testing conventions). |
| 4. Mart | Create `models/marts/<table>.sql` (or merge into an existing mart). |
| 5. Sync | Add a row to `pipelines/sync-engine/src/config/sync_jobs.yaml`: `bq_view`, `pg_table`, `primary_key`. That's the only place a new BQ→Postgres sync is registered — `bq_to_postgres.py` just reads this list, there's no separate allowlist to touch. |

**Gap today — no scheduled pipeline.** Root `Taskfile.yml` has no `ingest-daily` (or equivalent) composed task yet — only `lint`/`typecheck`/`test`/`coverage`/`integration-test`, and each service's own `ci` task (what `.github/workflows/ci.yml` actually runs). Until a composed ingest task exists, run each stage by hand:

```bash
# 1. ingest → GCS
task ingestion:build
docker run --rm -v $PWD/pipelines/ingestion-engine:/app -w /app ingestion-engine-dev uv run python src/main.py

# 2. GCS → BQ (manual, see step 2 above)
bq load --source_format=PARQUET raw_nba_api.<table> gs://hoop-brain-raw-data/nba-api/<table>.parquet

# 3-4. staging → mart
task transformation:build
docker run --rm -v $PWD/pipelines/transformation-engine:/app -w /app transformation-engine-dev dbt build --profiles-dir profiles

# 5. sync → Postgres
task sync:build
docker run --rm -v $PWD/pipelines/sync-engine:/app -w /app sync-engine-dev uv run python src/main.py
```

**Files to touch:** ingestion-engine module, `sources.yml`, dbt staging + mart models, `sync_jobs.yaml`.

---

## 2. New Analytical Model (its own Docker container, nested under model-engine)

For things like RAPM, BPM, traits, surplus value — anything that reads from marts/Postgres and writes derived output. **Each analytical model is a self-contained Docker container living as a subdirectory of `pipelines/model-engine/`** — e.g. `pipelines/model-engine/rapm/`, `pipelines/model-engine/traits/` — never a shared module inside one monolithic model-engine service. Each subdir has its own `Dockerfile`, `pyproject.toml`/`uv.lock`, `src/`, `tests/`, and `Taskfile.yml`, same shape as `ingestion-engine`/`sync-engine` today, just nested one level deeper.

**Planned but not built yet:** a `model-engine` orchestrator app responsible for facilitating deployment and running of each model subdirectory/container (discovering models, building/running each one, sequencing across them). Until that exists, treat each `pipelines/model-engine/<name>/` subdir as fully independent and drive it directly through its own Taskfile — don't block on the orchestrator to ship a model.

| Step | What to do |
|------|------------|
| 1. Scaffold | Copy an existing model subdir (or the template — see gap below) to `pipelines/model-engine/<name>/` (e.g. `pipelines/model-engine/rapm/`). Rename the package in `pyproject.toml` and update `[tool.setuptools] package-dir` if needed. Keep the same Dockerfile/Taskfile shape as `ingestion-engine`/`sync-engine` — don't reinvent it. |
| 2. Module | Write the model in `pipelines/model-engine/<name>/src/main.py` (or split into modules under `src/`). Read from BQ marts or Postgres; write to a derived table, e.g. `player_season_<metric>`. |
| 3. Shared code | No shared helper library exists yet. Duplicate the small amount of BQ/Postgres I/O boilerplate per model rather than building an abstraction — revisit only once 3+ models make the duplication genuinely painful, per this repo's own convention against premature abstraction. If the future orchestrator app ends up owning this I/O layer, that supersedes duplicating it per model. |
| 4. Tests | Unit tests on synthetic fixtures under `pipelines/model-engine/<name>/tests/` — boundary behavior (trait thresholds, cap rule edges, etc.) is the whole point. |
| 5. Wire the run path | Add a `run-main` task to the new service's `Taskfile.yml`, e.g. `docker compose run --rm <service> uv run python src/main.py` (mirrors `sync-engine`'s `run-main`). Without this there's no way to actually execute the model via Task. |
| 6. CI checks | Add a `ci` task to the new service's `Taskfile.yml` (`task: lint`, `task: typecheck`, `task: test`, `task: coverage`), mirroring `ingestion-engine`'s `ci` task. `.github/workflows/ci.yml`'s matrix calls `task <namespace>:ci` directly — without this task, CI has nothing to run for the new service. |
| 7. Root Taskfile | Add a new entry under `includes:` in the root `Taskfile.yml` pointing at the nested path (e.g. `model-<name>: {taskfile: ./pipelines/model-engine/<name>/Taskfile.yml, dir: ./pipelines/model-engine/<name>}`) — without this, `task model-<name>:build` won't resolve; Task only knows about namespaces explicitly listed there. |
| 8. Sync | If the API needs the output in Postgres, add it to `sync_jobs.yaml` (§1 step 5). |
| 9. API | Expose via a new/updated endpoint if the frontend needs it (§4). |

**Gap today — no template subdir, no orchestrator, no scheduled pipeline.** `pipelines/model-engine/` today is still a flat stub (`Dockerfile`/`Taskfile.yml`/`pyproject.toml`/`src/main.py` directly at that level, no subdirectories) — it hasn't been restructured into the nested shape above yet. Do that restructuring — move the stub's contents into a `pipelines/model-engine/_template/` subdir and update the root `Taskfile.yml` to match — as part of building the *first* real model, rather than as a no-op refactor now. Until then, run a model manually the same way as the other pipelines:

```bash
task model-<name>:build
docker run --rm -v $PWD/pipelines/model-engine/<name>:/app -w /app model-<name>-dev uv run python src/main.py
```

**Config keys:** the new service's `Taskfile.yml`, root `Taskfile.yml`, `sync_jobs.yaml`. Avoid hardcoding table names in the model.

---

## 3. Postgres Schema Change

### 3a. New table (via sync from BQ)
Covered in §1 step 5 — a new table arrives through `sync_jobs.yaml`, and `bq_to_postgres.py` creates it automatically on first sync (see `_atomic_swap` in that file).

### 3b. Altering an existing table
Worked example: CAL-144 added `league` to `Team`.

| Step | What to do |
|------|------------|
| 1. Model | Edit the SQLAlchemy model, e.g. `api/app/models/team.py`. |
| 2. Shell in | `docker compose exec api /bin/bash` — migrations run **inside the container**, never on host. |
| 3. Generate | `uv run alembic revision --autogenerate -m "add league to teams"`. |
| 4. Review | Open the generated file under `api/alembic/versions/` and actually read it — autogenerate gets server defaults, enum handling, and index changes wrong often enough that you must check it, not just run it. |
| 5. Apply | `uv run alembic upgrade head`. |
| 6. Schema | Update the matching Pydantic schema in `api/app/schemas/` if the field is API-exposed. |

---

## 4. New/Updated API Endpoint

| Step | What to do |
|------|------------|
| 1. Route | Create `api/app/api/routes/<module_name>.py` (e.g. `teams.py`). Define `@router.get("/")` or `@router.get("/{id}")` etc. |
| 2. Schema | Add `api/app/schemas/<module_name>.py` with Pydantic models. Use `from_attributes=True` for ORM. |
| 3. Model | If it's a new table, add `api/app/models/<module_name>.py` and an Alembic migration (§3b). |
| 4. Register | In `api/app/api/api_v1/api.py`: `from app.api.routes import <module_name>` then `router.include_router(<module_name>.router, prefix="/<resource>", tags=["<resource>"])` (e.g. module `teams` → prefix `/teams`). |
| 5. Test | Add `api/tests/test_<resource>.py`. Assert status and shape. |

Two easy-to-forget conventions (see CLAUDE.md API conventions): every response carries `league`, and any model-derived field carries provenance (model name + version) — not just a bare number.

---

## 5. New Frontend Page

Reflects what's actually installed today (`web/package.json` has neither React Router nor TanStack Query yet — the frontend PRD's target state for those lands in phase F0). Follow `web/src/components/TeamsTable.tsx` as the real precedent until then.

| Step | What to do |
|------|------------|
| 1. Component | Create the page component under `web/src/components/`. Fetch with a relative URL (e.g. `/api/v1/teams/`) so the Vite dev-server proxy to the api container works. |
| 2. State | `useState` for the fetched data, `useEffect` to trigger the fetch. Handle loading and error states explicitly — `TeamsTable.tsx` currently doesn't, don't copy that gap forward. |
| 3. Test | Add a colocated `<Component>.test.tsx` (vitest + RTL), matching `TeamsTable.test.tsx`. |
| 4. Nav | Wire it into the app shell (`App.tsx`) so it's reachable — there's no router yet, so this may just be a conditional render or a new top-level section. |

Once React Router and TanStack Query are installed (F0), this section should be rewritten to use them — don't write against libraries that aren't in `package.json` yet.

---

## Config Cheat Sheet

| Config | Purpose |
|--------|---------|
| `sync_jobs.yaml` | BQ view → Postgres table mapping. Add new rows for new entities. |
| `<service>/Taskfile.yml` | Per-service task definitions (lint, typecheck, test, coverage, `ci`, `run-main`). Every new `pipelines/model-engine/<name>/` needs its own Taskfile with at least `build`, `lint`, `typecheck`, `ci`. |
| Root `Taskfile.yml` (`includes:` + composed tasks) | Maps `task <name>:...` to a service directory, and composes cross-service tasks (`lint`, `test`, `integration-test`, and eventually `ingest-daily`). Every new `pipelines/model-engine/<name>/` needs its own `includes:` entry here or `task model-<name>:build` won't resolve. |
