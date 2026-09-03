# Hoop Brain API

FastAPI app, deployed to Vercel against Neon Postgres. See `CLAUDE.md` at the repo root for architecture and `docs/hoop-brain-backend-prd.md` for scope.

## Interacting with the deployed API

**Base URL:** `https://api-rho-umber-13.vercel.app`

Every `/api/v1/*` route requires an `X-API-Key` header — this is a single shared secret (not per-user auth; see `app/core/security.py`), meant to keep anonymous traffic off a personal tool, not to protect sensitive data. `/health`, `/docs`, `/redoc`, and `/openapi.json` don't require it.

```bash
# Health check (no key needed)
curl https://api-rho-umber-13.vercel.app/health

# Teams (key required)
curl -H "X-API-Key: <the key>" https://api-rho-umber-13.vercel.app/api/v1/teams/

# Filter by league
curl -H "X-API-Key: <the key>" "https://api-rho-umber-13.vercel.app/api/v1/teams/?league=WNBA"
```

Get the key from the Vercel dashboard (Project `luna-7cf6/api` → Settings → Environment Variables → `API_KEY`), or `vercel env pull` if you have the CLI linked.

**Interactive docs:** `/docs` (Swagger UI) and `/redoc` — both open, no key needed, since they only expose schema, not data.

## Local development

```bash
task build          # build the api-dev image
task lint            # ruff format --check
task typecheck        # ruff check
task integration-test # pytest against a real DB via docker compose
```

To run a single test directly instead: `uv run pytest tests/test_teams.py::test_read_teams` (needs `DATABASE_URL` + `API_KEY` in the environment — see `.env.example`).

Local requests also need `X-API-Key`, matching whatever `API_KEY` is set in your environment (tests default to `test-key` — see `tests/conftest.py`).

## Deploying

Linked to Vercel project `luna-7cf6/api` (Root Directory: `api`), connected to this GitHub repo for auto-deploy on push to `main`. Env vars (`DATABASE_URL`, `API_KEY`, optionally `CORS_ORIGINS`) are set in the Vercel dashboard, not committed.

**If deploying manually from a git worktree:** Vercel's CLI resolves the project's base path by walking up from `--cwd` looking for a `.git` *directory* — a linked worktree only has a `.git` *file* (pointing at the real repo), so this walk lands on the *main checkout's* `api/`, not the worktree's, and silently deploys stale code with no error. Point `--cwd` directly at the worktree's `api/` directory (not the repo root) and temporarily clear the project's Root Directory setting (`vercel project update api --auto-detect root-directory`) for that deploy, then restore it (`vercel project update api --root-directory api`) afterward — the GitHub-integration flow clones fresh each time and isn't affected by this.
