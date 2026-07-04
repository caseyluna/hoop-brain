# hoop-brain — Frontend PRD

**Version:** 1.0 · **Status:** Draft for review · **Scope:** Everything built on top of the backend API. This document is written to be handed to Claude Design, which will generate the actual UI, and to guide the user's own implementation work in the existing `web` app (React + TypeScript + Vite + Tailwind).

---

## 1. Purpose & UX Goals

hoop-brain gives its user one place to evaluate NBA and WNBA players and teams — stats, contracts, cap, trade value — instead of hopping across a dozen sites, so they can **get better at player evaluation and thinking like a GM and form their own informed, defensible takes.** That is the design brief's throughline, and it implies a specific stance: this UI is not for browsing basketball data, it's for _assessing_ it. Every screen should help the user answer "is this good or bad, and why" quickly enough that their attention goes to the judgment, not the gathering.

UX goals, in testable form:

- **U1 — Time-to-take.** From landing on a Player Page, the user can articulate a defensible first take on the player (good/bad, at what price, in what role) in under a minute, and locate the evidence for it in under three.
- **U2 — No tab-hopping.** A normal player or team evaluation never requires leaving the app or assembling information across more than one screen plus its own drill-downs.
- **U3 — Disagreement is supported.** Every model-derived signal (trait tag, grade, fit read, surplus value) exposes its reasoning on demand — the UI presents first-pass assessments the user can interrogate, not verdicts to accept. This is what makes the app a judgment-sharpening tool rather than an oracle.
- **U4 — League clarity.** At no point can the user be unsure whether they're looking at NBA or WNBA data.

**Non-goals:** journaling/take-logging UI, GM-quiz features (the user has a separate system for study workflow); mobile-optimized layouts at v1 (see §8); admin/multi-user surfaces.

## 2. Design Direction

**Brand: Hoop Brain.** Color palette open within the direction below (a wordmark/identity pass is an early Claude Design task, not a blocker).

**Modern SaaS product feel — Linear/Notion-ish.** Clean, confident, information-dense without clutter. Restrained palette where color means something (signal, status, league) rather than decoration. Strong typographic hierarchy so a page's "verdict layer" reads before its "evidence layer." Generous but efficient spacing. Explicitly avoid sports-broadcast visual clichés: no team-color gradients everywhere, no jersey textures, no ESPN-style density-by-chaos. The reference feeling: an internal tool a real front office would respect.

**Both dark and light mode, user-toggleable.** Build on a token system from the first component (all color as semantic tokens, never hardcoded) so both themes are first-class; dark as the default is a reasonable starting point given the reference aesthetic, with the toggle persistent in the shell.

**The organizing mental model — "topline, then portals."** In the user's own words: a top-line idea of a player, and then portals to look into and dig deeper. Every entity page is a compact verdict layer at the top (what is this player/team, in one glance) with each summary element acting as a _portal_ — an entry point that opens into its own deeper layer (a trait tag opens its statistical basis; a contract snapshot opens the full cap detail; a headline stat opens the trend and splits behind it). "Dense but calm": the topline is calm, the density lives inside the portals, and the user chooses when to descend.

Two color systems carry meaning and must never be conflated:

- **Signal colors** (good/neutral/bad) for assessments — surplus value, grades, fit reads, cap health.
- **League identity** — a subtle but persistent NBA vs. WNBA distinction (e.g., an accent tint on the league badge/context bar), never applied to signal.

Numbers are the content here: tabular figures, aligned columns, percentile context next to raw values wherever a raw value alone would require league knowledge to interpret.

**Show position in a distribution, not just a number.** Whenever the underlying question is "compared to whom?" — how good is this stat, how does this player fit this team, where does this contract sit league-wide — the answer is a _visual placement_ (percentile profile, distribution strip, gap chart, scatter position) with the number alongside it. Raw values require league knowledge to interpret; placed values _build_ league knowledge, which is this app's actual job. Every core surface carries at least one such visual: the Player Page's percentile profile, the Team Fit gap chart, the leaderboard distribution strip, the surplus scatter, the comparison overlay (see §4 and the component inventory).

## 3. Information Architecture

```
App shell
├── League context (persistent, global: NBA | WNBA)
├── Global search (players, teams — always reachable)
├── Players
│   └── Player Page  ← the core surface
│        ├── Team Fit (embedded tool)
│        └── Game log / splits (drill-down)
├── Teams
│   └── Team Page
│        └── Cap sheet (deep view)
├── Tools
│   ├── Trade Machine
│   └── Comparison
├── Leaderboards (rank by any metric / trait / valuation)
└── Explore (discovery/search — later phase)
```

**League switching** is a global, persistent control in the shell — not a per-page setting. Switching league switches the whole context (search scope, lists, defaults). Every entity page also carries a league badge locally so a deep-linked page is never ambiguous. Cross-league views don't exist; the UI never mixes leagues in one list or comparison.

**Navigation principle:** entity-first, not feature-first. The user's mental model is "let me look at this player / this team"; tools (fit, trade, compare) attach to entities or take entities as inputs, rather than being destinations you fill in from scratch.

## 4. Screen Specifications

Phasing mirrors the backend roadmap. Each spec gives purpose, the information hierarchy (primary → secondary → drill-down — this ordering is the spec, not a suggestion), key interactions, and acceptance criteria.

### Phase 1 — Foundation (ship first; must stand alone as useful)

#### 4.1 Player Page — the core surface of the entire product

**Purpose:** the one place to evaluate a player. Reads as a first-pass assessment the user can agree or disagree with — not a stat dump.

**Information hierarchy:**

- **Primary (the verdict layer — visible without scrolling):**
  - Identity strip: name, headshot, team, position, age, league badge.
  - **Assessment header:** trait/archetype tags (e.g., `3&D Wing`, `Rim Protector`) + the generated "what they bring / what they don't" strengths-weaknesses summary. This is the page's headline, not a sidebar widget.
  - **Contract/cap snapshot:** current salary, years remaining, and — once available — surplus-value read with signal color. Cap context is prominent per the user's #1 priority; a player is never shown detached from what they cost.
  - **Percentile profile (visual):** the player's statistical shape at a glance — a compact chart (horizontal percentile bars grouped by skill area, or a radar) of league-relative percentiles across the key dimensions (scoring, efficiency, playmaking, rebounding, defense, usage). This is the single fastest "what kind of player is this" read on the page and sits in the verdict layer beside the trait tags (the tags are, in effect, labels the taxonomy attached to this shape — seeing shape and tags together is how the user learns to see what the model sees, and to disagree with it).
  - Season topline: a small set of headline stats with league-percentile context (the percentile is what makes a raw number assessable at a glance).
- **Secondary (one scroll down):** season-by-season stat table (box/advanced/impact tabs within the table, not page tabs); trend sparklines (rolling windows, grades over the season); availability/games-played context.
- **Drill-down (on demand):** full game log with per-game grades; shot/skill detail as backend data expands; "how is this calculated?" expanders on every model-derived value (serves U3 directly).
- **Embedded tool:** **Team Fit picker** (spec 4.6) lives on this page, collapsed by default.

**Interactions:** trait tags are hoverable/expandable to show the statistical basis (which percentiles triggered the tag); percentile bars accompany key stats; everything model-derived has provenance on demand.

**States:** data-coverage flags from the API render as honest, quiet "not yet available" affordances (e.g., contract snapshot pre-Stage-8) — never fake-empty zeros, never layout collapse.

**Accepts when:** U1's time-to-take test passes with realistic data; the assessment header is the first thing a new viewer reads; no information needed for a normal evaluation requires leaving the page.

#### 4.2 Team Page

**Purpose:** evaluate a team the way a front office would — roster construction and cap position first, performance second.

**Information hierarchy:**

- **Primary:** identity strip (league badge, record); **cap position summary** — total salary, cap room / tax distance, apron status with proximity indicator, committed years — with signal color on cap health; roster health topline (count, surplus-value rollup once available).
- **Secondary:** roster table (player, position, age, salary, years, trait tags, surplus signal — each row is a compressed player card linking to 4.1); depth chart view (toggle from the roster table, same data re-grouped by position).
- **Drill-down:** the **full cap sheet** — multi-year grid of every contract (guarantees, options, dead money), exceptions available, and future commitments. This is a first-class deep view, not a footnote: for priority #1, this grid is the product.
- Team performance trends live below the roster material, deliberately — this app's lens is construction over results.

**Accepts when:** the user can answer "what is this team's cap situation and where is their roster value concentrated?" from the primary + secondary layers alone.

### Phase 2 — Tools on the foundation

#### 4.3 Leaderboards

**Purpose:** compare players across the whole league on any dimension — metrics, traits, roles, valuations — the fastest way to build the cross-league context that individual player pages can't provide. ("Who are the best rim protectors?" "Where does this contract rank among wings?")

**Layout:** one flexible ranked-table surface, not many hardcoded boards. Controls: metric picker (box / advanced / impact / — once available — surplus value), optional trait/role filter (rank only "3&D wings"), and the standard filters (position, team, age, minutes threshold). Rows are compact player cards (name, team, the ranked value with percentile bar, salary context) linking to 4.1. League-scoped always — an NBA board and a WNBA board, never one mixed list.
**Interactions:** every board state is URL-addressable (shareable/bookmarkable — "my custom board" without a save feature); column-click re-ranking; minutes threshold defaulted sensibly to keep low-sample noise out, adjustable with the low-confidence styling from §7 when loosened. Each board carries a **distribution strip** for the ranked metric — the league's distribution with the visible players marked on it — so "ranked 12th" also reads as _how far_ 12th is from 1st and from average (rankings hide gaps; distributions show them).
**Data:** `GET /leaderboards` (available with the Player Page — this can ship alongside Phase 1, and should be treated as the third foundation surface if sequencing allows). Valuation boards light up automatically when surplus data lands.
**Accepts when:** any "rank X by Y filtered to Z" question expressible in the controls is answerable in under three interactions; boards are deep-linkable.

#### 4.4 Contracts / Surplus Value views

**Purpose:** make production-vs-salary visible as shape, not just as numbers — the most direct "check my take against the data" surface in the app.

**Core visualization:** a production-vs-salary scatter (per league, per season): each dot a player, axes = projected production value and actual salary, the diagonal = fair value; above the line = surplus, below = overpay. Filterable by team, position, trait, contract years remaining. Clicking a dot opens the player's card/page.
**Secondary:** rankable league-wide lists (best/worst value contracts) derived from the same data; a per-team surplus rollup that links back to 4.2.
**Accepts when:** the user can find "underpaid wings on expiring deals" in a few interactions, and every point of interest is one click from the underlying evidence.

#### 4.5 Trade Machine

**Purpose:** build multi-team trades and _reason_ about them — legality and value both — with feedback while building, because the reasoning happens during construction, not after submission.

**Phasing (decided):** **v1 ships as a two-team builder** with the column layout designed for N teams from the start (adding a team = adding a column, not a redesign). Multi-team, pick protections, and exception-path suggestions layer in later. Phase the UI as much as needed — a rock-solid two-team experience beats a shaky four-team one.

**Layout:** one column per team; each column shows outgoing/incoming assets and a live before/after mini cap sheet. A persistent **legality bar** across the top re-evaluates on every change: green/red with _specific_ violations named ("Team A is over the first apron and cannot aggregate salaries"), not a bare fail. A **value read** alongside legality: surplus-value delta per team, framed as information for the user's judgment ("Team B gives up more expected value") — never "this trade is bad."
**Interactions:** add players from roster pickers (search within team); add draft picks; violations update live and link to the rule they cite (learning surface, per U3).
**Accepts when:** a real historical trade can be reconstructed and validates correctly; an illegal variation shows the specific violated rule; the user never has to "submit and see."

#### 4.6 Team Fit picker (embedded in the Player Page)

**Purpose:** "would this player make sense on that team?" — instantly, from wherever the user already is (the player's page).

**Layout:** collapsed control → team selector → result panel with two labeled reads: **Cap feasibility** (can they realistically acquire him: room/exception/trade-match paths, from the same backend logic as 4.5) and **On-court fit** (what he adds vs. what they have — trait-gap based at first, lineup-data-driven later). The on-court read is anchored by a **trait-gap visual**: the team's current trait/percentile mix and the player's profile shown against each other, so surplus ("adds elite rim protection they lack") and redundancy ("third high-usage creator") are _visible_, not just asserted. Both reads always show their _reasoning_ — the traits/gaps/cap facts driving them — never a bare score.
**Progressive enhancement rule:** the component renders whatever explanation structure the API returns. The backend upgrades this model in tiers over time; the UI must not encode assumptions about tier — when richer fit data lands, this component gets better without changing.
**Accepts when:** any player → any team returns both reads with visible reasoning in one interaction; the Tier-2 backend upgrade requires zero frontend changes.

### Phase 3 — Expanded surfaces

#### 4.7 Comparison view

Side-by-side (2–3 players, or 2 teams), same league only: **overlaid percentile profiles** (the same chart as 4.1, players layered in distinct hues — differences in shape are the comparison) above stat rows with per-metric advantage highlighting, trait tags aligned for gap-spotting, contract/surplus context always included (never compare production without cost). Entry points: from any Player/Team page ("compare with…"), from search, and from any leaderboard row.

#### 4.8 Discovery / search

Global search (name, always available in the shell) plus filtered discovery: position, age, trait tags, contract situation (expiring, team-option, min-salary), surplus range. The query "show me available rim protection under $10M" should be expressible in filters. Results as compact player cards → 4.1.

#### 4.9 Context & splits

Layered onto existing pages rather than new destinations: splits (home/away, vs. quality opponents, clutch) as expandable sections within the Player Page's stat area; availability history within the player header's drill-down. New top-level pages are a last resort.

## 5. Component Inventory (shared across screens and leagues)

One system, league-parameterized — nothing is built twice for NBA/WNBA:

| Component                                       | Used by                                    | Notes                                                                                                                       |
| ----------------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| League badge / context bar                      | everywhere                                 | The U4 guarantee.                                                                                                           |
| Player card (compact)                           | rosters, search, comparison, trade columns | Name, position, salary, trait chips, surplus signal.                                                                        |
| Trait chip                                      | 4.1, cards, comparison, fit                | Hover/expand → statistical basis.                                                                                           |
| Stat table w/ percentile context                | 4.1, 4.2, 4.3, 4.7                         | Tabular numerals; percentile bar inline.                                                                                    |
| Percentile bar                                  | stat tables, headers                       | Always league-scoped; labeled as such.                                                                                      |
| **Percentile profile chart**                    | 4.1 (verdict layer), 4.7 (overlaid)        | The "player shape" visual: grouped percentile bars or radar; single-player and multi-player-overlay modes of one component. |
| **Distribution strip**                          | 4.3, player/contract headers               | League distribution of a metric with entities marked on it; shows gaps that rankings hide.                                  |
| **Trait-gap chart**                             | 4.6                                        | Team trait mix vs. player profile; surfaces additions and redundancies visually.                                            |
| **Production-vs-salary scatter**                | 4.4                                        | Fair-value diagonal; dots are players; click-through to 4.1.                                                                |
| Cap sheet grid                                  | 4.2, 4.5                                   | Multi-year; option/guarantee glyphs; the same component at two sizes (mini in trade columns, full on Team Page).            |
| Signal badge (good/neutral/bad)                 | surplus, grades, fit, legality             | The only place signal colors appear.                                                                                        |
| Provenance expander ("how is this calculated?") | every model-derived value                  | U3's implementation; renders model name/version + components from API provenance fields.                                    |
| Data-coverage notice                            | anywhere a domain isn't populated yet      | Honest, quiet, consistent.                                                                                                  |
| Trend sparkline                                 | 4.1, 4.2                                   | Rolling windows, grade sequences.                                                                                           |
| Team/player selector                            | 4.5, 4.6, 4.7                              | Search-driven, league-scoped.                                                                                               |

## 6. Data Dependencies (per screen → backend API)

| Screen                             | Requires (backend PRD §9)              | Frontend can ship after backend stage |
| ---------------------------------- | -------------------------------------- | ------------------------------------- |
| App shell + league switch + search | `GET /teams`, `GET /players`           | Stage 1                               |
| Player Page (stats + traits)       | `GET /players/{id}/profile`, `/games`  | Stage 6                               |
| Leaderboards                       | `GET /leaderboards`                    | Stage 6 (valuation boards at 8)       |
| Player Page (contract snapshot)    | profile's contract fields              | Stage 8                               |
| Team Page + cap sheet              | `GET /teams/{id}/roster`, `/cap-sheet` | Stage 8                               |
| Surplus views                      | `/surplus` endpoints                   | Stage 8                               |
| Trade Machine                      | `POST /trades/evaluate`, cap-sheet     | Stage 9                               |
| Team Fit picker                    | `GET /players/{id}/fit/{team_id}`      | Stage 9 (Tier 1)                      |
| Comparison, Discovery              | `/compare`, `/search`                  | Stage 10+                             |
| Splits                             | splits fields on existing endpoints    | Stage 10+                             |

Gaps found while implementing a screen (a field the design needs that the API doesn't return) are flagged against the backend PRD's API surface — that table is the shared contract, and it changes deliberately, not ad hoc.

## 7. States & Edge Cases (system-wide)

- **Loading:** skeletons matching final layout; no spinner-only pages.
- **Partial data:** the norm during buildout — data-coverage notices per §5, never fake zeros, never broken layouts. Design every screen for its partial state first, since that's the state it will live in longest.
- **Low-confidence model outputs:** where the API flags low sample (e.g., low-minutes players) or model uncertainty, the UI shows it (muted signal color + a flag), because overconfident presentation of weak data corrupts exactly the judgment this app exists to sharpen.
- **Stale data:** contract `last_verified_at` beyond a threshold renders a staleness hint on cap surfaces.
- **Empty search/filters:** suggest loosening specific filters rather than a bare "no results."

## 8. Platform & Implementation Assumptions

- **Desktop-first, mobile-eventual (decided).** Layouts target ≥1280px and that's where design effort goes; but because mobile is a stated future direction, build the cheap foundations now — fluid layouts over fixed widths, no hover-only interactions for essential actions, components that stack sensibly — so "eventually mobile" is a layout pass, not a rebuild. Phone-optimized layouts remain out of v1 scope.
- **Theming:** semantic design tokens from the first component; dark and light are both first-class with a persistent toggle (see §2).
- **Stack:** the existing `web` app — React + TypeScript + Vite + Tailwind — extended, not replaced. Claude Design output should be compatible with this stack and structured as components matching §5's inventory, so generated screens and hand-written code share one system.
- **Charts:** pick one library (recharts is the natural fit for this stack) and use it everywhere; no per-screen chart-library decisions.
- **State:** server data via a query-caching layer (e.g., TanStack Query) rather than hand-rolled fetch/useState as screens multiply; trivial today, decide before Phase 2 tools add mutation-like flows (trade builder state).

## 9. Decisions Log & Remaining Open Questions

**Resolved (user decisions, July 2026):**

1. **Theme:** dark and light, user-toggleable; token-based from the start (§2).
2. **Brand:** Hoop Brain; colors open within the §2 direction — an identity/wordmark pass is an early Claude Design task.
3. **Default league on open:** NBA (persist last-used thereafter is a reasonable refinement).
4. **Trade Machine:** phased — two-team v1, N-team-ready layout (§4.5).
5. **Density:** "dense but calm" confirmed, articulated as the topline-and-portals model (§2) — validate against the first Player Page mockup before the pattern propagates.
6. **Platform:** desktop-first now, mobile eventually — foundations laid, phone layouts deferred (§8).
7. **Leaderboards:** first-class surface (§4.3), effectively a third foundation screen since its API ships with the Player Page.

**Still open:**

1. Wordmark/identity and the specific accent palette (Claude Design's first deliverable alongside the Player Page).
2. Whether the leaderboard's default metric per league should be an internal model (BPM) or a pulled one (DARKO DPM) — decide when both columns exist.
