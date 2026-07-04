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

Docker Compose locally; Dagger orchestration + CI (`services.yaml`, `pipelines.yaml`); scheduled ingestion via GitHub Actions. Extension pattern is documented in `docs/ADDING_FEATURES.md` — follow it for every new source, model, endpoint, and page.

**Division of computation (a rule):** heavy compute (aggregation, model fitting, percentiles) happens batch in BigQuery/dbt/model-engine; Postgres holds pre-computed read-optimized results; the API does only cheap request-time work. Exceptions (user-chosen inputs, so request-time by necessity): trade validation and Team Fit — both read pre-computed inputs and apply rules logic. Doubly important on Vercel serverless. Use pooled Postgres connections always.

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

- **Testing:** every ingestion source gets a schema test; every dbt staging model gets uniqueness/not-null tests on its dedupe key; every model-engine module gets unit tests on synthetic fixtures (boundary behavior on trait thresholds and cap rules is the whole point); API keeps its integration-test pattern. Run per-service via existing Taskfiles/Dagger.
- **Tickets:** work from Linear. Small, single-session issues (≤ S); anything larger is broken into sub-issues. Each ticket carries big-picture context, technical context, steps, DoD, and a test — read it fully before starting; if it conflicts with this file's Current state, flag the conflict, don't silently pick one.
- **Scope discipline:** if a ticket's scope creeps mid-implementation, stop and flag — small chippable pieces are a deliberate choice. Don't gold-plate; don't build ahead of the current stage.
- **This is a learning project as much as a shipping one:** when work involves a real design decision (modeling choice, schema tradeoff, statistical method), briefly explain the decision and why — don't just implement silently. Prefer approaches Casey can understand end-to-end over clever opacity.
- **Source etiquette:** honor ToS (Crafted NBA prohibits scraping — use its published formulas instead), rate-limit everything, cite Her Hoop Stats, prefer official download paths (DARKO CSV) over scraping.

## Current state (UPDATE THIS as work lands)

As of 2026-07-04: only `Team` works end-to-end (ingest → BQ → sync → Postgres → API → bare React table) and it **lacks the league field** — that fix is Stage 0, first ticket. `get_players()` exists in `ingestion-engine/src/modules/nba_api.py` but nothing downstream consumes it. `model-engine` and dbt are stubs. CI/lint/test scaffolding is mature across services. Nothing is deployed to Vercel/Neon yet. Roadmap: Stage 0 (league foundation) → 1 (Player + entity resolution) → 2 (scheduling + deploy) → 3 (games/box + WNBA) → 4 (pbp/lineups) → 5 (impact models + traits) → 6 (profile API + leaderboards = MVP) → 7 (grades/trends) → 8 (contracts/cap/surplus) → 9 (Team Fit + Trade Machine) → 10+ (expansion). Frontend phases: F0 foundations → F1 core views → F2 tools → F3 expanded.
