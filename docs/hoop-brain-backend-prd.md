# hoop-brain — Backend PRD

**Version:** 1.0 · **Status:** Draft for review · **Scope:** Everything through the API layer. UI/UX is covered in the companion Frontend PRD.

---

## 1. Problem & Purpose

Evaluating an NBA or WNBA player or team today means hopping across many sites: one for box and advanced stats, another for shot data, another for contracts and cap sheets, another for impact metrics, another for lineup data. The gathering consumes the attention that should go into the judgment.

hoop-brain exists to fix that, in service of one goal: **make its user a sharper evaluator and front-office thinker — someone who can form their own informed, defensible takes on players, teams, contracts, and trades.** The backend's job is to aggregate everything about a player or team into one queryable place, and to compute the derived models (traits, surplus value, cap feasibility, trade legality) that let the user compare and value players, teams, and scenarios. Every model in this document is a first-pass assessment the user can agree with, disagree with, or dig underneath — never a replacement for their judgment.

The user's ranked priorities — an ordering of what to build first, all serving the one goal above:

1. Roster construction, cap & contracts
2. Trade & draft-pick valuation
3. Talent evaluation / traits
4. Custom advanced metrics

**Not this system's job:** logging the user's takes, journaling, or GM-quiz features. The user has a separate personal system for study workflow. This is the data and judgment-support layer used _while_ forming takes, not where takes are recorded.

## 2. Goals & Success Criteria

The backend is succeeding when:

- **G1 — One place.** For any NBA or WNBA player, a single API call (or small set) returns bio, contract/cap detail, stats across levels (box, advanced, impact), trait tags with a strengths/weaknesses summary, and availability — with no need to consult external sites for a normal evaluation.
- **G2 — Comparison and valuation work.** The user can compare any two players or teams on the same normalized metrics, see surplus value, check whether a player fits a team (cap + on-court), and validate a multi-team trade's legality — all against the same underlying data layer, computed once.
- **G3 — Trustworthy identity.** Every player is one entity internally, regardless of how many sources reference them, and no NBA/WNBA data is ever conflated.
- **G4 — Sustainable solo maintenance.** Data refreshes on a schedule without manual babysitting; contract data (the one domain requiring manual curation) has a clear override path; nothing depends on paid feeds.

Concrete acceptance test for the MVP milestone (end of Stage 6): _pick any active NBA player; hit the player profile endpoint; the response alone is enough to form and defend a take on whether they're a good player and (once Stage 8 lands) whether their contract is good value — without opening another website._

## 3. Users & Consumers

- **The user** — a solo, analytically sophisticated builder-operator. Works in short, infrequent sessions; the system must be resumable without re-deriving context.
- **The frontend** — a React app (built via Claude Design) consuming this API. The API surface in §9 is the contract between the two PRDs.
- **Future consumers** — the user's own notebooks/scripts for custom metric experiments (priority 4). The API and marts should be queryable directly for this; no special work required beyond clean schemas.

## 4. Architecture (existing — extend, don't replace)

The stack is already built and deliberately chosen:

```
ingestion-engine (Python) → Parquet in GCS → BigQuery raw_<vendor> datasets
  → transformation-engine (dbt: staging → marts)
  → sync-engine (config-driven, sync_jobs.yaml) → Postgres
  → api (FastAPI + SQLAlchemy + Alembic) → web (out of scope here)
```

Containerized via Docker Compose; CI'd via Task (root `Taskfile.yml` composing each service's own `Taskfile.yml`); lint/typecheck/test per service. The extension pattern is documented in `docs/ADDING_FEATURES.md` and every stage spec below is written in its terms:

- **New data source:** ingest method in `pipelines/ingestion-engine/src/modules/` → GCS → BQ raw → dbt staging (dedupe) → dbt mart → `sync_jobs.yaml` entry → pipeline wiring.
- **New model:** its own self-contained container as a subdirectory of `pipelines/model-engine/` (`pipelines/model-engine/<name>/`), reading from marts/Postgres, writing a derived table → wired into the root `Taskfile.yml`'s `includes:` → synced to Postgres if the API needs it. A `model-engine` orchestrator app to facilitate deploying/running each model subdirectory is planned but not yet built.
- **New endpoint:** route in `api/app/api/routes/` → Pydantic schema → SQLAlchemy model + Alembic migration if a new table → registered in `api/app/api/api_v1/api.py` → test in `api/tests/`.

**Linear project structure (execution layer over this PRD's stages):** this document stays the scope-and-why reference; Linear organizes the actual tickets across several projects, not one flat backlog. **Hoop Brain — Data Platform & API** owns raw ingestion through a deployed, queryable API (Stages 0–4, plus contract/cap *source data* from Stage 8) — nothing derived or trained. **Hoop Brain — Data Transformation** owns feature engineering and aggregation (rate stats, possession aggregation, percentiles, pre-aggregated app-facing tables) — the marts every model and the eventual frontend read from. Every metric/engine that used to live inside one monolithic "model-engine" stage is now its **own Linear project and its own Docker container** (`pipelines/model-engine/<name>/`): BPM/VORP, RAPM, EPM, Traits, Surplus Value, Pick Valuation, Cap Feasibility Engine, and Draft Prospects — each with a DoD of "runs end-to-end via one task command, output synced and served through an API endpoint." Composed/cross-model features that need several of those projects to exist first (the unified Player Profile, Leaderboards, Team Fit, Trade Machine, Game Grades) sit unassigned in the Linear backlog, picked up once their dependencies are real — see §13 for when and why this split happened.

**Verified current state:** only `Team` works end-to-end, and it has no league field. `Player` ingestion exists in `nba_api.py` but is not wired downstream. `model-engine` and dbt are stubs. This PRD's roadmap starts exactly there.

**Deployment (decided):** the API deploys to **Vercel** (FastAPI runs fine as Vercel Python serverless functions) so it's reachable from anywhere; **scheduled ingestion stays in GitHub Actions** driving the Dagger pipelines against GCP (GCS/BigQuery), which is already the repo's shape — no new orchestrator needed. Two consequences to design for: (1) Postgres must live in a managed host reachable from Vercel (Neon is the natural fit — serverless-friendly, free tier, built-in connection pooling; Supabase or Cloud SQL also work), and sync-engine writes to it from GHA; (2) serverless + SQLAlchemy requires pooled connections (Neon's pooler or pgbouncer) — configure this from day one, not after the first connection-exhaustion bug.

**Division of computation** (a rule, not a suggestion): heavy computation (stat aggregation, model fitting, percentiles) happens in BigQuery/dbt/model-engine, batch, ahead of time. Postgres holds pre-computed, read-optimized results. The API reads Postgres and performs only cheap request-time work. The two exceptions — computations that must happen at request time because their inputs are user-chosen — are trade validation and Team Fit, both of which read pre-computed inputs (cap sheets, trait profiles) and apply rules logic in the API layer. This division matters doubly on Vercel, where request-time compute is the wrong place for anything heavy.

## 5. Domain Model

All entities are league-aware from the root. `league` is an enum (`NBA`, `WNBA`) — never nullable, never inferred.

| Entity                      | Key fields                                                                                                          | Notes                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Team**                    | `id`, `league`, `full_name`, `abbreviation`, `city`, ...                                                            | Exists today minus `league` — see Stage 0.                                        |
| **Player**                  | `id` (internal surrogate), `league`, `full_name`, `birthdate`, `position`, `height`, `current_team_id`, `is_active` | Internal ID is _not_ any source's ID — see §6.                                    |
| **PlayerSourceMapping**     | `internal_player_id`, `league`, `source`, `source_id`, `match_method`, `confidence`, `matched_at`                   | The entity-resolution backbone. Unique on (`league`,`source`,`source_id`).        |
| **PlayerMatchCandidate**    | candidate pair + score + status (`pending`/`confirmed`/`rejected`)                                                  | Review queue for below-threshold matches.                                         |
| **Season**                  | `id`, `league`, `year_label`, start/end dates                                                                       | NBA and WNBA seasons are different rows; nothing joins across them.               |
| **Game**                    | `id`, `league`, `season_id`, `game_date`, home/away team ids                                                        |                                                                                   |
| **PlayerGameStats**         | `player_id`, `game_id`, box-score fields                                                                            | Mart-derived; per-100 and TS%/eFG% added in dbt.                                  |
| **Contract / ContractYear** | player, team, per-year salary, guarantees, options, source, `manual_override` flag                                  | Maintained internal dataset (§7), not a pure ingest.                              |
| **CapRulesConfig**          | `league`, `season_id`, cap, tax line, apron thresholds, matching-rules parameters                                   | Rules as _versioned data_, so a rule change is a config edit, not a code change.  |
| **DraftPick**               | `league`, year, round, owning team, protections                                                                     | Enters at Stage 9 (trade machine needs it).                                       |
| **Derived model tables**    | `player_season_<metric>`, `player_traits`, `player_surplus_value`, `lineup_possessions`, etc.                       | Written by model-engine/dbt; versioned where the methodology can change (traits). |

**Compatibility note:** the user maintains a separate Notion knowledge system with Player/Team entities. This schema should not contradict it (same conceptual entities, league-tagged), but no sync is built — out of scope.

## 6. Entity Resolution

The identity problem is structural, not hypothetical: the NBA stats API has its own numeric player IDs; a WNBA source will have a different vendor's scheme; contract data is scraped from sites with no shared ID at all, matched by name. Getting this wrong silently corrupts everything downstream — surplus value attached to the wrong player is worse than no surplus value.

Design:

1. **Internal surrogate `player_id`** — all internal tables key on it. No table other than `PlayerSourceMapping` ever stores a raw source ID.
2. **`PlayerSourceMapping`** maps `(league, source, source_id) → internal_player_id`, with the match method and confidence recorded. League is always part of the key; NBA and WNBA players are never cross-matched, even on identical names — they are different people by definition here.
3. **Tiered matching**, most to least reliable:
   - **Tier 1 — authoritative passthrough.** When a source is the system of record for a league (the NBA stats API for NBA), its ID maps 1:1 with confidence 1.0. No fuzzy logic.
   - **Tier 2 — deterministic.** Cross-vendor sources with enough identity data: normalized full name + birthdate + league. Birthdate resolves nearly all name collisions.
   - **Tier 3 — fuzzy.** When a source lacks birthdate (typical for scraped contract sites): name similarity + current team + position, producing an explicit confidence score.
   - **Tier 4 — human review.** Below a confidence threshold (start at 0.90, tune with experience), the match is _not_ auto-resolved. It's written to `PlayerMatchCandidate` for one-click confirmation. This is a data-integrity decision: a small manual step on ambiguous identity beats silent misattribution. (This is distinct from — and does not violate — the "no manual trait tagging" rule; confirming identity is fixing data, not authoring opinion.)
4. **Idempotent re-runs.** Resolution runs as part of ingestion pipelines; re-running never creates duplicate internal players.

Acceptance criteria for the design overall: ingesting the same player from two sources produces one internal player with two mappings; a contract row for a common-name player attaches to the right internal player or lands in the review queue — never guesses.

## 7. Data Sourcing Strategy

**The full source-by-source menu — every named site, access method, cost, and recommended role — lives in the companion document `hoop-brain-data-source-catalog.md`.** This section is the strategy layer over that catalog.

| Domain                                                                 | Strategy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Freshness / risk                                                                                                                                                                                    |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rosters, teams, box & advanced stats, play-by-play, shot data, lineups | **Free/API.** NBA: the `nba_api` ecosystem (already in use). WNBA: stats.wnba.com via the sportsdataverse/`wehoop` ecosystem, behind the same adapter interface.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Daily scheduled ingest. Risk: unofficial endpoints change without notice → pipeline failure alerts (already partially wired via GHA notifications).                                                 |
| Contracts, cap sheets, future salary years, exceptions                 | **Scrape + maintain as an internal dataset.** No clean free API exists. Scraped seed (Spotrac, cross-validated against RealGM and HoopsHype as a tertiary source) + `manual_override` on every row; overrides always win over re-scrapes. Treated as a curated table, not a one-time import.                                                                                                                                                                                                                                                                                                                                                                                                                                   | The highest-priority _and_ highest-maintenance domain. Staleness is dangerous (a wrong salary breaks trade validation), so every contract row carries `last_verified_at`, surfaced through the API. |
| Cap/CBA rules (thresholds, apron restrictions, matching rules)         | **Build as versioned config** (`CapRulesConfig`), populated from current authoritative references (e.g., the current CBA FAQ) — never from memory or stale notes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Changes ~annually per league; WNBA CBA is currently in flux — see WNBA note below.                                                                                                                  |
| Player biographical depth (birthdates especially) + historical impact comps | **One-time/occasional curated import from Basketball-Reference**, at very low request rates per their ToS — birthdates feed entity resolution's Tier 2 matcher; historical BPM/VORP/Win Shares serve as a rebuild cross-check. Not a recurring pipeline job. | Low risk (infrequent, small volume), but respect the low-rate constraint strictly — this is a "labor of love" site, not an API.                                                                     |
| Availability (injuries, transactions, roster moves)                    | **Pipeline.** Official NBA/WNBA transaction + injury feeds; RealGM's transactions pages as documented backup.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Feeds the profile's availability section and roster-freshness triggers; source endpoints still need to be pinned down (tracked as its own ticket, not assumed).                                    |
| Draft prospect evaluation (college/international pre-draft production) | **New domain, added after initial PRD planning.** Its own model project (Hoop Brain — Model: Draft Prospects) translates pre-draft statistical production to NBA/WNBA outcome projections — distinct from pick *valuation* (which prices the pick slot, not the player). Needs its own ingestion source, chosen via ADR (no source vetted yet, unlike contracts) — candidates include Bart Torvik/T-Rank, Sports Reference's college site (ToS to verify), NCAA stats, ESPN's undocumented API. Prospects get a pre-draft entity-resolution tier, matched to their internal `player_id` once drafted. | New, unvalidated pipeline — expect the ADR + first ingestion pass to surface real friction (ToS, coverage gaps) before this is reliable.                                                            |
| Impact metrics                                                         | **Build, one Docker container + Linear project per metric** (BPM/VORP, RAPM, EPM — no longer one bundled model-engine stage): BPM/VORP-family from box score; RAPM once lineup data exists; then **rebuild the paid metrics** — an EPM-style metric (RAPM with a statistical-plus-minus prior, per the published methodology) and optionally a LEBRON-style variant. **Decided: paid impact metrics are recreated, not subscribed to** — partly to avoid dependencies, mostly because rebuilding them is itself the learning goal (understanding a metric deeply enough to implement it is exactly the priority-4 skill). Free pulled metrics (DARKO CSV, nbarapm.com, FiveThirtyEight RAPTOR archives) and public leaderboards serve as validation baselines for each rebuild. | Reproducible, no external dependency.                                                                                                                                                               |
| Traits, surplus value, pick valuation, Team Fit, trade legality        | **Build**, each (except Team Fit/trade legality, still composed/deferred — see §13) its own model project. Nothing external provides these.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Core IP of the project.                                                                                                                                                                             |
| Tracking / play-type / proprietary impact data (paywalled)             | **Optional plug-ins only.** Nothing in the core may depend on them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | None at MVP.                                                                                                                                                                                        |

**Budget posture:** hybrid and cheap — free ecosystem for stats, internal curated dataset for contracts, ~$0–20/mo. No enterprise feeds.

**Historical depth is metric-driven:** ingest as far back as the chosen models require (aging curves and comparables want ~15–20 seasons of box data; lineup-era models are bounded by play-by-play availability; contracts are forward-looking plus a few seasons back). Don't hardcode a window; each stage states its own depth requirement.

**Pull-in metrics worth knowing about (see catalog for detail):** DARKO DPM is a **free nightly CSV download keyed to NBA player IDs** — a trivial, high-value pipeline add and a cross-check for internal models. Dunks & Threes EPM has an official paid API (optional plug-in, never a dependency, parked pending a subscription decision). BBall Index's LEBRON is a similar optional Patreon plug-in, explicitly never a dependency. Crafted NBA prohibits scraping but publishes its formulas — rebuild those in model-engine (which is priority #4 anyway).

**WNBA reality check, revised:** stats coverage is good, and **the contract/cap data problem is largely solved by the Her Hoop Stats Salary Cap Database** — publicly viewable, independently maintained per-team cap sheets and player salaries (cite as requested), paired with their WNBA CBA FAQ as the rules source. The cap engine remains **NBA-first** in rules depth, but the WNBA contract dataset should seed from HHS rather than being written off as unavailable. The WNBA CBA is mid-transition — re-verify rules on every encoding pass.

## 8. Roadmap — Stage Specs

Each stage is independently useful, sized for incremental solo sessions, and states its dependencies. Stage order tracks the user's priority ranking under the constraint of data dependencies (you can't value contracts before players and stats exist).

**Reading this against Linear:** stages 0–4 (plus contract *source data* from Stage 8) map to Hoop Brain — Data Platform & API. Feature-engineering work that used to be folded into a stage's dbt steps (rate stats, possession aggregation, percentiles) is now Hoop Brain — Data Transformation's job. Stage 5, the cap-engine/surplus half of Stage 8, and Stage 9's pick valuation are each their own Hoop Brain — Model: `<name>` project. Stage 6, 7, and the rest of Stage 9 (Team Fit, Trade Machine) describe *composed* endpoints that read from several of those model projects — real scope, but deliberately left unassigned in Linear until enough of their dependencies exist to build them for real, not dropped.

### Stage 0 — League foundation _(do first; cheap now, expensive later)_

Add `league` (non-nullable enum) to `Team`; Alembic migration backfilling existing rows to `NBA`; carry `league` through ingestion → staging → mart → sync → API schema. Establish the internal-ID convention (§6) before `Player` lands.
**Depends on:** nothing. **Accepts when:** `GET /teams` returns `league` on every row; migration is reversible; the ID strategy is written into the repo docs.

### Stage 1 — Player entity, league-aware, with entity resolution built in

Wire the existing `get_players()` ingestion end-to-end (GCS → BQ → `stg_players` → `players` mart → sync → Postgres → `GET /players`), with the internal surrogate ID and `PlayerSourceMapping` from day one — retrofitting resolution later would mean re-keying every downstream table.
**Depends on:** Stage 0. **Accepts when:** all active NBA players queryable via API with internal IDs; the NBA source mapping table is populated at confidence 1.0; re-running ingest creates zero duplicates.

### Stage 2 — Scheduled ingestion

Turn ingestion from manual runs into scheduled pipelines (Dagger pipelines + the existing GHA scheduled-workflow foundation), with failure alerting. Every later stage's data plugs into this scheduler rather than adding its own.
**Depends on:** Stage 1. **Accepts when:** players/teams refresh daily unattended; a failed run produces a notification.

### Stage 3 — Games & box scores, and the WNBA adapter _(decided: WNBA lands here, not later)_

Game schedule + player game logs ingested; `stg_games`, `stg_game_details`; `player_game_stats` and `team_game_results` marts (including TS%, eFG%, per-100 in dbt); sync + `GET /games`, `GET /players/{id}/games`. Historical backfill depth: as far as the Stage 5 models require.
**This stage also brings the WNBA online:** a `wehoop`/stats.wnba.com source adapter behind the same interfaces (teams, players, games, box scores), proving the league abstraction while the pipeline pattern is fresh rather than retrofitting it at Stage 10. WNBA player ingestion routes through the same entity-resolution machinery (its own authoritative source IDs, Tier 1, league-scoped).
**Depends on:** Stages 1–2. **Accepts when:** any NBA _or WNBA_ player's game log is queryable with derived rates; dbt tests pass on dedupe keys; no shared code path assumes NBA.

### Stage 4 — Play-by-play & lineups

Play-by-play ingestion; a lineup/possession builder (parse substitutions into stints: who was on the floor, points for/against); data-quality validation (exactly 5 per side per stint, spot-checks vs. a reference source).
**Depends on:** Stage 3. **Accepts when:** `lineup_possessions` exists and passes validation. _This is the hardest data-engineering stage in the project — play-by-play parsing is notoriously fiddly. Budget accordingly and don't block Stage 5's box-score models on it (see below)._

### Stage 5 — Impact models & traits _(each metric is now its own project + container, not one model-engine stage)_

Four deliverables, each its own Hoop Brain — Model: `<name>` Linear project with its own `pipelines/model-engine/<name>/` container, deliberately decoupled so box-score work isn't blocked by Stage 4:

- **5a. Box-score impact — Hoop Brain — Model: BPM/VORP:** BPM → VORP (and optionally Win Shares) from Stage 3 data.
- **5b. Lineup impact — rebuild the paid metrics — Hoop Brain — Model: RAPM, then Hoop Brain — Model: EPM:** RAPM first (design matrix from stints/possessions, which now live in Hoop Brain — Data Transformation; ridge regression; validate against public RAPM sets — nbarapm.com, FiveThirtyEight RAPTOR archives); then an **EPM-style rebuild** (RAPM with an SPM prior built from the estimated-skills approach described in the public methodology); a LEBRON-style variant later if wanted. Each rebuild validates against its public reference (DARKO's free CSV, published EPM leaderboards) — agreement builds trust, disagreement is studied, not hidden. Needs Stage 4 + Data Transformation's possession aggregation.
- **5c. Trait taxonomy (v1) — Hoop Brain — Model: Traits:** a _versioned_ config defining a finite tag set — **decided: start with 10 tags per league** (e.g., "3&D wing," "high-usage creator," "rim protector"), expanding only after living with them — as explicit rules over **league-relative percentiles** (computed in Hoop Brain — Data Transformation; NBA and WNBA percentile pools are never mixed). Output per player-season: tags + a structured strengths/weaknesses summary generated from the same rules (high-percentile traits = brings; low-percentile in relevant categories = doesn't). Fully data-derived; no manual tagging path exists. Versioned so threshold tuning never silently rewrites historical labels. Part of validating v1: compare tag assignments against publicly discussed archetypes (the user explicitly wants to see where their data-derived tags agree and disagree with public consensus — the disagreements are the learning).

Each project's own DoD: runs end-to-end via one task command (`task model-<name>:run-main`), writes its derived table, syncs to Postgres, and serves through its own API endpoint — not bundled into a shared composed endpoint (that's Stage 6).
**Depends on:** 5a/5c on Stage 3 + Data Transformation; 5b on Stage 4 + Data Transformation. **Accepts when:** `player_season_bpm_vorp`, `player_traits`, `player_season_rapm`/`player_season_epm` (as each project completes) exist, run via their own task command, and are synced; a spot-check of ~20 well-known players produces face-valid tags.

### Stage 6 — Player profile API & leaderboards _(the MVP milestone; composed, currently unassigned in Linear)_

One composed endpoint, `GET /players/{id}/profile`, assembling: bio, current contract snapshot, season + recent stats, impact metrics, trait tags + strengths/weaknesses, availability. Response shape designed with the Frontend PRD's Player Page as the driving consumer.
**Also ships here: `GET /leaderboards`** — league-scoped, rankable views over the derived tables: any metric (box/advanced/impact), any trait (e.g., all "rim protectors" ranked by chosen metric), filterable by position/team/age/minutes, with percentile context. Cheap to build (pure reads over Stage 3/5 tables) and high-value for the comparison goal; surplus-value and valuation leaderboards extend it automatically when Stage 8 lands.
**This is real, spec'd scope — not dropped — but it composes across multiple Stage 5/8 model projects, so it stays unassigned in Linear until enough of them exist to build it against real data rather than placeholders.**
**Depends on:** Stages 1, 3, 5a/5c (contract fields join in at Stage 8; the shape reserves room for them, returning `null` + a data-coverage flag until then). **Accepts when:** the G1 acceptance test in §2 passes for stats/traits; response < 500ms from pre-computed tables.

### Stage 7 — Game grades & season trends _(composed, currently unassigned in Linear)_

Per-game grade (game score vs. player baseline → letter grade) and rolling trend windows (5/10/20 games), exposed on the game-log endpoints.
**Depends on:** Stage 3 (better with 5a). **Accepts when:** game logs include grades and trend deltas. Unassigned in Linear alongside Stage 6, for the same reason — pending the impact-metric baseline it grades against.

### Stage 8 — Contracts, cap & surplus value _(priority #1 domain — deepest design attention; split across three Linear homes)_

**8a. Contract & cap source data — Hoop Brain — Data Platform & API:**

- **Contract dataset:** scraped seed + manual-override curation per §7, resolved to internal player IDs via §6 (this is where Tier 3/4 matching earns its keep). NBA seed: Spotrac cross-validated against RealGM and HoopsHype as a tertiary source. **WNBA seed: the Her Hoop Stats Salary Cap Database** (see catalog).

**8b. Cap Feasibility Engine — Hoop Brain — Model: Cap Feasibility Engine** _(rules logic, not a trained model — its DoD is adapted: "runs via a simple task command for local testing," not "train + predict")_:

- **CapRulesConfig:** current-CBA thresholds and rules for NBA (cap, tax, first/second apron, exception sizes, salary-matching parameters), sourced from current authoritative references (Larry Coon's CBA FAQ for NBA; the Her Hoop Stats CBA FAQ for WNBA). WNBA rules depth grows as the new CBA settles.
- **Cap engine, phased:** (i) team cap-sheet computation — totals by year, room, tax distance, apron proximity, dead money; (ii) apron-dependent restriction logic. Basic before exotic.
- **Reusable cap-feasibility function:** `can_team_acquire(team, incoming, outgoing, context) → legal | violations[]`. Built _here_, as one function with multiple callers — Stage 9's Team Fit and trade machine both consume it rather than duplicating rules. Likely lives as a plain Python module the API imports directly, not a Docker container, since it's request-time business logic (see §4's division of computation) — confirmed during this project's own tickets, not assumed upfront.

**8c. Surplus value — Hoop Brain — Model: Surplus Value:**

- **$/win decided: derive internally.** Compute the league's going rate from public league salary data (total league salaries against total available wins/impact above replacement per season), rather than adopting a published number. More work, but league-consistent, WNBA-portable by construction, and — importantly for the actual goal — the user understands every step of it. Cross-check the output against DARKO's published "Fair Salary" as an external sanity reference. Surplus = projected production at that rate minus salary, per player-season, rolled up per roster.

**Depends on:** Stages 5a, 6 for 8c's production side; 8a for both 8b and 8c's cap-hit side. **Accepts when:** `GET /teams/{id}/cap-sheet` returns a full multi-year sheet with apron status; surplus value ranks a roster; the feasibility function has unit tests covering the CBA rule set, sourced against current references.

### Stage 9 — Team Fit, Trade Machine & pick valuation _(pick valuation is its own project; Team Fit/Trade Machine are composed, currently unassigned in Linear)_

- **Team Fit** (`GET /players/{id}/fit/{team_id}`), two honest tiers behind one stable response shape: **Tier 1** = cap feasibility (Stage 8b's function) + trait-complementarity heuristic (does this player's archetype fill a gap in the team's trait mix); **Tier 2** = upgrade the on-court component with real lineup data (Stage 5b) — a drop-in enrichment, not a new endpoint. The response always includes the _explanation_ (which traits/gaps/cap facts drive the read), never a bare score. **Composed across the Cap Feasibility Engine and Traits/RAPM projects — unassigned in Linear until those exist**, same reasoning as Stage 6/7.
- **Trade Machine** (`POST /trades/evaluate`): multi-team proposal in → legality (salary matching per apron status, hard-cap triggers, pick rules e.g. Stepien) + per-team before/after cap sheets + surplus-value delta out. Pure function over Stage 8 data — no state. **Also composed (Cap Feasibility Engine + Surplus Value) — unassigned in Linear for the same reason.**
- **DraftPick** entity + pick valuation — **Hoop Brain — Model: Pick Valuation**, its own project (distinct from Draft Prospect Evaluation below, which values the *players*, not the *pick slots*). **Decided: simple historical EV curve at v1** (expected value by draft slot from historical outcomes), protection-aware simulation as a later upgrade. Note the league difference: WNBA picks can only be traded one draft ahead (per the HHS CBA FAQ) — the rules config, not shared code, carries this.
  **Depends on:** Stage 8 (Tier 2 additionally on 5b). **Accepts when:** known-legal and known-illegal real trades validate correctly against the rules config; fit responses are explanation-bearing; the frontend needs no changes when Tier 2 lands.

### Stage 9b — Draft Prospect Evaluation _(new domain — Hoop Brain — Model: Draft Prospects; not part of the original PRD planning)_

Added after the initial roadmap was written: a statistical translation model projecting how draft-eligible prospects (college, international, G-League) will perform at the NBA/WNBA level from their pre-draft production — the kind of methodology Crafted NBA's prospect model publishes (§7), rebuilt rather than pulled. **Distinct from Stage 9's pick valuation**, which prices the *pick slot* as a trade asset — this prices the *player* being drafted.

- **College basketball ingestion** (Hoop Brain — Data Platform & API): source not yet vetted, unlike contracts — an ADR picks between Bart Torvik/T-Rank, Sports Reference's college site, NCAA stats, and ESPN's undocumented API before anything is scraped. Needs its own pre-draft entity-resolution tier (college player → internal `player_id`, resolved once the player is actually drafted).
- **Rate-adjusted college marts** (Hoop Brain — Data Transformation): per-40, per-100, TS%, usage estimate — the same treatment Stage 3 gives pro game logs.
- **Translation model** (Hoop Brain — Model: Draft Prospects): trained on past draft classes' pre-draft stats vs. their actual NBA/WNBA outcomes, predicting current-class prospects; validated by cross-checking translated projections for 2–3 past classes against those players' real rookie production.

**Depends on:** the college ingestion ADR + pipeline; entity resolution's existing tiered-matching machinery (§6), extended with the pre-draft tier. **Accepts when:** `task model-draft-prospects:run-main` runs end-to-end and projections for the current draft class are queryable via the API.

### Stage 10+ — Expansion _(in priority order, each independently shippable)_

Expanded ingestion (shot charts → shot-quality model, tracking, hustle — each feeding richer traits); comparison/discovery endpoints (side-by-side, filterable search including by trait and cap situation); context & splits (clutch, opponent-adjusted, garbage-time filtering, availability history); model explainability (component storage so "how is this calculated?" is answerable — directly serves the learning goal); player similarity/comps; protection-aware pick simulation. Deliberately coarse, unassigned in Linear — sliced at kickoff, not before.

## 9. API Surface (the contract with the Frontend PRD)

All under `/api/v1`, league-scoped explicitly (decide the mechanism once, in Stage 0 — recommendation: explicit `league` query param on list endpoints, never silently defaulting to NBA).

| Endpoint                                               | Purpose                                                               | Available from         |
| ------------------------------------------------------ | --------------------------------------------------------------------- | ---------------------- |
| `GET /teams`, `GET /teams/{id}`                        | Team list/detail, league-tagged                                       | Stage 0                |
| `GET /players`, `GET /players/{id}`                    | Player list (filterable) / detail                                     | Stage 1                |
| `GET /players/{id}/games`                              | Game log + grades/trends                                              | Stage 3 / 7            |
| `GET /players/{id}/profile`                            | The composed evaluation payload                                       | Stage 6                |
| `GET /leaderboards`                                    | Rankable views: any metric/trait/valuation, league-scoped, filterable | Stage 6 (extends at 8) |
| `GET /teams/{id}/cap-sheet`                            | Multi-year cap sheet, apron status                                    | Stage 8                |
| `GET /teams/{id}/roster`                               | Roster with contract + trait summaries                                | Stage 8                |
| `GET /players/{id}/surplus`, `GET /teams/{id}/surplus` | Surplus value, player & roster level                                  | Stage 8                |
| `GET /players/{id}/fit/{team_id}`                      | Team Fit (tiered, explanation-bearing)                                | Stage 9                |
| `POST /trades/evaluate`                                | Trade legality + impact                                               | Stage 9                |
| `GET /prospects/{id}/college-stats`                    | Pre-draft college season line                                         | Stage 9b               |
| `GET /compare?players=…` / `?teams=…`                  | Side-by-side comparison                                               | Stage 10+              |
| `GET /search`                                          | Cross-entity discovery with filters                                   | Stage 10+              |

Conventions: every response carries `league`; every model-derived field carries enough provenance to answer "where did this number come from" (model name + version at minimum); data-coverage flags (`contract_data: "unavailable"`) instead of silent nulls where a domain isn't populated yet.

## 10. Cross-Cutting Requirements

- **League separation** is enforced at the schema level (non-nullable enums, league in every unique key), not by convention. Percentile computations, cap rules, and entity resolution are always league-scoped. No aggregate ever mixes leagues.
- **Data freshness is user-visible.** `last_updated` on synced marts and `last_verified_at` on contracts flow through the API, because a stale cap number should look stale when the user is forming a take on it.
- **Testing conventions:** every ingestion source gets a schema test; every dbt staging model gets uniqueness/not-null tests on its dedupe key; every model-engine module gets unit tests on synthetic fixtures (especially trait thresholds and cap rules, where boundary behavior is the whole point); the API keeps its existing integration-test pattern.
- **Determinism/versioning:** model outputs record model version; trait-taxonomy changes bump a version rather than mutating history.

## 11. Non-Goals

Take-logging/journaling; GM-quiz or prompt-and-grade features; Notion sync; multi-user auth/accounts (single-user assumption — flagged in §13); paid-data integrations as dependencies; real-time/live-game data (daily freshness is the target); betting-oriented features.

## 12. Risks

| Risk                                                         | Severity                                                          | Mitigation                                                                                                                               |
| ------------------------------------------------------------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Unofficial stats endpoints change/break                      | High likelihood, medium impact                                    | Adapter isolation per source; scheduled-run failure alerts; raw parquet preserved so backfills re-run from GCS.                          |
| Contract data staleness/wrongness                            | Medium likelihood, **high** impact (poisons cap, surplus, trades) | Manual-override-wins curation; `last_verified_at` surfaced; trade validation warns on stale inputs.                                      |
| Cap rules encoded wrong                                      | Medium/high impact                                                | Rules as versioned config sourced from current references; unit tests against real known-legal/illegal trades; never encode from memory. |
| Play-by-play parsing (Stage 4) balloons                      | High likelihood, medium impact                                    | Decoupled from 5a/5c so box-score value ships regardless; validation gate before anything consumes lineup data.                          |
| Entity-resolution false positives                            | Low likelihood if tiers respected, high impact                    | Review queue below threshold; confidence stored; mappings auditable and reversible.                                                      |
| Scope gravity toward "interesting models" over the core goal | Chronic                                                           | Every stage's acceptance criteria trace to §2's goals; the §2 MVP test is the arbiter.                                                   |

## 13. Decisions Log & Remaining Open Questions

**Resolved (user decisions, July 2026):**

1. **Deployment:** API on Vercel; scheduled ingestion via GHA → Dagger → GCP (see §4, including the managed-Postgres and connection-pooling requirements this creates).
2. **$/win for surplus value:** derived internally from public league salary data; DARKO's Fair Salary as an external cross-check (see Stage 8).
3. **Trait taxonomy:** 10 tags per league at v1, tuned by living with them; validated partly by comparison against publicly discussed archetypes (see Stage 5c).
4. **Pick valuation:** simple historical EV curve first; protection-aware simulation later (see Stage 9).
5. **WNBA adapter:** Stage 3, alongside games/box scores (see Stage 3).
6. **Leaderboards:** first-class feature from Stage 6, extending with valuations at Stage 8.
7. **Paid impact metrics (EPM, LEBRON):** rebuilt in model-engine from published methodologies rather than subscribed to — recreating them is itself the learning goal; free public data (DARKO CSV, public leaderboards) used as validation baselines.
8. **Project structure (August 2026):** analytical models are no longer one shared "model-engine" stage — each metric/engine is its own Linear project and its own self-contained Docker container (`pipelines/model-engine/<name>/`), with a DoD of "runs via one task command, output synced and served through the API." A `model-engine` orchestrator app to facilitate building/running each container is planned but not yet built.
9. **Data Transformation split out as its own project/layer**, sitting between raw ingestion and the model projects: feature-engineered marts for models to query (rate stats, possession aggregation, percentiles) *and* pre-aggregated tables for the (later) frontend to read without request-time aggregation.
10. **Composed/cross-model features deferred, not dropped:** the unified Player Profile, Leaderboards, Game Grades, Team Fit, and Trade Machine (Stages 6, 7, 9) sit unassigned in the Linear backlog until enough of their model-project dependencies exist to build them against real data — see the "Reading this against Linear" note at the top of §8.
11. **Draft Prospect Evaluation added as new scope** (Stage 9b): a statistical translation model for pre-draft prospects, its own Linear project, distinct from pick valuation. Requires a new college-basketball ingestion source, not yet chosen.
12. **Cap Feasibility Engine gets its own Linear project despite being rules logic, not a trained model** — its DoD is adapted (a task command for local testing, not train+predict) and it likely stays a plain Python module in the API codebase rather than a Docker container, since it's request-time business logic (§4).

**Still open:**

1. The specific v1 tag list for the trait taxonomy (a Stage 5c design session — the user wants to formulate it once the data is visible).
2. Managed-Postgres provider choice (Neon recommended; decide at Stage 0/1 when sync-engine's target moves off local).
3. pbpstats API vs. building the possession parser in-house (evaluate at Stage 4 kickoff — see catalog).
4. Whether Dunks & Threes EPM or BBall Index's LEBRON ever become paid plug-ins, or DARKO + internal models suffice.
5. College basketball data source for Stage 9b (Bart Torvik/T-Rank vs. Sports Reference vs. NCAA vs. ESPN) — resolved via its own ADR before any scraping starts.
6. Whether Cap Feasibility Engine ends up as a Docker container after all, or stays a plain API-embedded module — confirm during its own tickets rather than assuming either way upfront.
