# CLAUDE.md — Hoop Brain

Auto-loaded context for Claude/Cursor sessions in this repo. Purpose: Casey works in short, infrequent sessions — this file plus the current Linear ticket should be enough to resume work cold, with zero re-explaining. Keep the **Current state** section updated as work lands; everything else changes rarely.

**Source-of-truth documents** (commit these to `docs/` and keep them there):

- `docs/hoop-brain-backend-prd.md` — data platform & API scope, stage-by-stage
- `docs/hoop-brain-frontend-prd.md` — UI scope, screen-by-screen (built with Claude Design)
- `docs/hoop-brain-data-source-catalog.md` — every data source, access method, and its assigned role

Linear is the source of truth for _what to do right now_; the PRDs are the source of truth for _scope and why_.

## What this app is

One place to evaluate NBA and WNBA players and teams — stats, contracts, cap, trade value — instead of hopping across a dozen sites. **The single most important goal: make Casey a sharper evaluator and front-office thinker who forms his own informed, defensible takes.** Every model here is a first-pass assessment he can agree with, disagree with, or dig underneath — never a replacement for judgment. If a piece of work doesn't serve "aggregate everything, help me evaluate and reason better," it doesn't belong.

Ranked priorities (build-order weighting, all serving the one goal): (1) roster construction, cap & contracts; (2) trade & draft-pick valuation; (3) talent evaluation/traits; (4) custom advanced metrics.

**Non-goals:** take-logging/journaling, GM-quiz features (Casey's separate Notion system handles study workflow), Notion sync, multi-user auth, real-time data, betting.

## Architecture (deliberate — extend, never propose alternatives)

```
ingestion-engine (Python) → Parquet in GCS → BigQuery raw_<vendor>
  → transformation-engine (dbt: staging → marts)
  → sync-engine (config-driven, sync_jobs.yaml) → Postgres (managed: Neon planned)
  → api (FastAPI + SQLAlchemy + Alembic, deploys to Vercel)
  → web (React + TS + Vite + Tailwind, built via Claude Design)
```

Docker Compose locally; Task (`Taskfile.yml`, one per service + a composing root file) drives both local dev checks and CI; scheduled ingestion via GitHub Actions. Extension pattern is documented in `docs/ADDING_FEATURES.md` — follow it for every new source, model, endpoint, and page. `model-engine` in the diagram above is not one shared service: each analytical model (RAPM, traits, surplus value, ...) is its own self-contained container living as a subdirectory of `pipelines/model-engine/` (`pipelines/model-engine/<name>/`), never a module bolted onto one monolithic model-engine. A `model-engine` orchestrator app to facilitate deploying/running each model subdirectory is planned but not yet built.

**Division of computation (a rule):** heavy compute (aggregation, model fitting, percentiles) happens batch in BigQuery/dbt/model-engine; Postgres holds pre-computed read-optimized results; the API does only cheap request-time work. Exceptions (user-chosen inputs, so request-time by necessity): trade validation and Team Fit — both read pre-computed inputs and apply rules logic. Doubly important on Vercel serverless. Use pooled Postgres connections always.

## Commands

Local dev: `docker compose up --build` runs `db` (Postgres), `api` (:8000), `web` (:5173, Vite), and a shell-only `sync-engine` container. Data persists in the `postgres_data` volume — no reseed needed between runs. Shell into a running service: `docker compose exec <service> /bin/bash`. New table → write the model, then run Alembic inside the `api` container (`alembic revision --autogenerate` / `alembic upgrade head`).

Root `Taskfile.yml` `includes:` every service's Taskfile and composes cross-service checks natively (no separate orchestrator):
- `task lint` / `task typecheck` / `task test` / `task coverage` — run that check for every service
- `task integration-test` — api DB migration against a test DB (via `docker compose run`), boots sync-engine, runs api integration tests

Per-service Taskfiles (`api/`, `web/`, `pipelines/{ingestion,model,sync,transformation}-engine/`) run the same checks locally via `task build` (builds a `<service>-dev` image) then `task lint` / `task typecheck` / `task <ns>:ci` (the exact composition CI runs) / `task all-checks`; Python services also have `task test` / `task coverage` (pytest under the hood). CI (`.github/workflows/ci.yml`) calls `task <ns>:build` then `task <ns>:ci` per service via a matrix, plus root `task integration-test` — same commands as local dev, just run by GitHub Actions instead of by hand.

To run a single Python test, bypass the Taskfile and call pytest directly, e.g. from `api/`: `uv run pytest tests/test_teams.py::test_list_teams` (or via the dev image: `docker run --rm -v $PWD:/app -w /app api-dev uv run pytest tests/test_teams.py::test_list_teams`).

web (`web/`, plain npm, no Docker wrapper needed for local dev — CI runs it through the `web-dev` image via the Taskfile): `npm run dev`, `npm run build`, `npm run test` (vitest), `npm run lint` (eslint), `npm run typecheck` (tsc --noEmit). Single test: `npm run test -- TeamsTable.test.tsx`.

transformation-engine (dbt): tasks are `dbt-parse`, `dbt-deps`, `dbt-test`, `dbt-build`, all run with `--profiles-dir profiles`.

Each service's own `Taskfile.yml` is the source of truth for what a task actually runs — check it before assuming a command exists.

## Repository map

- `api/app/` — FastAPI app. `api/routes/<resource>.py` (routers) → mounted in `api/api_v1/api.py` under `/api/v1`; `models/` (SQLAlchemy) + `schemas/` (Pydantic); `db/base.py` imports all models for Alembic autogenerate, `db/session.py` is the pooled engine/session. `alembic/` migrations run inside the api container, not on host. Today only `/health` and `/api/v1/teams` exist.
- `web/src/` — `components/` holds pages + UI (colocated `*.test.tsx`, vitest + RTL). Vite dev server proxies `/api/v1/...` to the api container (`API_PROXY_TARGET` in `docker-compose.yaml`) — always fetch with relative paths.
- `pipelines/<engine>/` — `ingestion-engine`, `model-engine`, `sync-engine` are independent uv-managed Python packages (own Dockerfile, `pyproject.toml`, `tests/`); `src/main.py` is the entrypoint each one's `run-main` job invokes. `sync-engine/src/config/sync_jobs.yaml` declaratively maps `bq_view → pg_table` (+ `primary_key`) — the only place new BQ→Postgres syncs get registered. `transformation-engine/` is the dbt project (`models/staging`, `macros`, `seeds`, `snapshots`, `profiles/profiles.yml`).
- Root `Taskfile.yml` composes every service's Taskfile (`includes:`) into the cross-service `lint`/`typecheck`/`test`/`coverage`/`integration-test` tasks that both local dev and `.github/workflows/ci.yml` run — no separate orchestrator layer.
- Root config = the extension surface (see `docs/ADDING_FEATURES.md`): each service's `Taskfile.yml` (job definitions, incl. the `ci` task CI actually calls), `pipelines/sync-engine/src/config/sync_jobs.yaml` (sync registrations).

## Two leagues, never conflated

NBA and WNBA share infrastructure but are separate leagues: separate CBAs, cap systems, seasons, sources. `league` is a non-nullable enum on every entity, part of every unique key. Percentiles, cap rules, and entity resolution are always league-scoped. No aggregate, comparison, or leaderboard ever mixes leagues. Cap engine is NBA-first in rules depth; WNBA contract data seeds from the Her Hoop Stats Salary Cap Database (cite them), rules from their WNBA CBA FAQ (CBA is mid-transition — re-verify on every encoding pass). NBA cap rules encode from Larry Coon's CBA FAQ — never from memory or training data; exact thresholds go stale silently.

## Entity resolution (identity is sacred)

Sources use non-matching player IDs (nba_api numeric IDs, WNBA vendor IDs, name-only contract scrapes). Internal surrogate `player_id` keys everything; `PlayerSourceMapping` (`internal_player_id, league, source, source_id, match_method, confidence, matched_at`) is the only table holding raw source IDs. Matching tiers: (1) authoritative passthrough (nba_api for NBA = confidence 1.0), (2) deterministic name+birthdate+league, (3) fuzzy with confidence score, (4) **below threshold → review queue, never auto-resolve.** NBA and WNBA players are never cross-matched. Ingestion re-runs must be idempotent — zero duplicate players.

## Key model decisions (see PRDs for full detail)

- **Traits:** fully data-derived, no manual tagging; a _versioned_ config of 10 tags per league over league-relative percentiles; strengths/weaknesses generated from the same rules; threshold tuning bumps the version, never rewrites history silently. Validate v1 against publicly discussed archetypes — disagreements are the learning.
- **Paid impact metrics are rebuilt, not bought:** RAPM, then EPM-style (RAPM + SPM prior), LEBRON-style later — from published methodologies, validated against DARKO's free CSV and public leaderboards. The rebuild is the point.
- **Surplus value:** $/win derived internally from public league salary data; DARKO "Fair Salary" as external cross-check.
- **Cap feasibility is one function** (`can_team_acquire`) with multiple callers (Team Fit, Trade Machine) — never duplicate rules logic.
- **Team Fit ships in two tiers** behind one stable API shape: cap + trait-gap heuristic first, real lineup data later; frontend must not change between tiers.
- **Pick valuation:** simple historical EV curve v1; protection-aware simulation later. WNBA picks trade only one draft ahead — the rules config carries this, not shared code.
- **Contracts are a curated dataset,** not a pure ingest: scraped seed (Spotrac + RealGM cross-validation; HHS for WNBA) + `manual_override` that always wins + `last_verified_at` surfaced through the API.

## Frontend principles (full detail in frontend PRD)

Brand: **Hoop Brain**. Modern SaaS (Linear/Notion-ish), dense but calm. Dark + light, token-based, toggleable. Desktop-first, mobile-eventual (fluid layouts, no hover-only essentials). Organizing model: **"topline, then portals"** — a calm verdict layer up top; every summary element is a portal into its deeper layer. **Show position in a distribution, not just a number** — percentile profiles, distribution strips, trait-gap charts, scatter placement. Signal colors (good/bad) and league identity colors are separate systems, never conflated. Every model-derived value has a "how is this calculated?" provenance expander. Charts: recharts. Server state: TanStack Query.

## API conventions

All under `/api/v1`. Every response carries `league`. Model-derived fields carry provenance (model name + version). Data-coverage flags (`contract_data: "unavailable"`), never silent nulls or fake zeros. Composed reads: `GET /players/{id}/profile` is the MVP payload; `GET /leaderboards` serves metric/trait/valuation rankings.

## Working conventions

- **Testing:** every ingestion source gets a schema test; every dbt staging model gets uniqueness/not-null tests on its dedupe key; every model-engine module gets unit tests on synthetic fixtures (boundary behavior on trait thresholds and cap rules is the whole point); API keeps its integration-test pattern. Run per-service via existing Taskfiles.
- **Tickets:** work from Linear. Small, single-session issues (≤ S); anything larger is broken into sub-issues. Each ticket carries big-picture context, technical context, steps, DoD, and a test — read it fully before starting; if it conflicts with this file's Current state, flag the conflict, don't silently pick one.
- **Scope discipline:** if a ticket's scope creeps mid-implementation, stop and flag — small chippable pieces are a deliberate choice. Don't gold-plate; don't build ahead of the current stage.
- **This is a learning project as much as a shipping one:** when work involves a real design decision (modeling choice, schema tradeoff, statistical method), briefly explain the decision and why — don't just implement silently. Prefer approaches Casey can understand end-to-end over clever opacity.
- **Source etiquette:** honor ToS (Crafted NBA prohibits scraping — use its published formulas instead), rate-limit everything, cite Her Hoop Stats, prefer official download paths (DARKO CSV) over scraping.

## Current state (UPDATE THIS as work lands)

As of 2026-07-04: only `Team` works end-to-end (ingest → BQ → sync → Postgres → API → bare React table) and it **lacks the league field** — that fix is Stage 0, first ticket. `get_players()` exists in `ingestion-engine/src/modules/nba_api.py` but nothing downstream consumes it. `model-engine` and dbt are stubs. CI/lint/test scaffolding is mature across services. Nothing is deployed to Vercel/Neon yet. Roadmap: Stage 0 (league foundation) → 1 (Player + entity resolution) → 2 (scheduling + deploy) → 3 (games/box + WNBA) → 4 (pbp/lineups) → 5 (impact models + traits) → 6 (profile API + leaderboards = MVP) → 7 (grades/trends) → 8 (contracts/cap/surplus) → 9 (Team Fit + Trade Machine) → 10+ (expansion). Frontend phases: F0 foundations → F1 core views → F2 tools → F3 expanded.
