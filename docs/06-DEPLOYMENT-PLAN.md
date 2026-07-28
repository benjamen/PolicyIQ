# Deployment Plan

## Environments

- **local**: `docker-compose.yml` — Postgres+pgvector, Redis, MinIO (R2-compatible local stand-in),
  backend, frontend dev server, one Celery worker + beat. `make up` / `make down`.
- **staging**: mirrors production topology at lower scale, seeded with a small insurer subset,
  used for extraction-quality review before a prompt/model change ships.
- **production**: managed Postgres (with pgvector extension) + managed Redis + Cloudflare R2 +
  containerized services on a small managed container platform (right-sized for real traffic —
  no Kubernetes cluster for Phase 1's traffic level; that's premature infrastructure for a beta
  product, revisit if/when scale demands it).

## Containers

`docker/`: `Dockerfile.backend`, `Dockerfile.worker` (shared base, different entrypoint per
Celery queue — crawler/downloader/extractor/embeddings run as separate queues so one slow stage
doesn't starve another), `Dockerfile.frontend` (multi-stage: Vite build → static served via
nginx or via the CDN in front of R2).

## CI/CD (GitHub Actions)

```
on: pull_request
  - lint (ruff, mypy for backend; eslint, vue-tsc for frontend)
  - unit tests (backend, workers, frontend)
  - integration tests (spin up postgres+redis via services:, run API + worker integration suite)
  - extraction eval (gold-set precision/recall — fails the build on regression, see
    05-AI-EXTRACTION-STRATEGY.md)
  - build all Docker images (no push)

on: push to main
  - all of the above
  - build + push images to registry, tagged with commit SHA
  - run Alembic migration check against a throwaway DB (catch broken migrations before deploy)
  - deploy to staging automatically
  - deploy to production: manual approval gate (this is a document-integrity product — no
    silent auto-deploys to prod until the platform has enough of a track record to trust that
    gate to automation)
```

## Database migrations

Alembic, one migration per PR touching schema, reviewed like code (not squashed). Migrations
run as a pre-deploy step, backward-compatible by convention (additive first, remove-old-column
in a follow-up release after the new column is in use) so rolling deploys never have a window
where old code hits a schema it doesn't understand.

## Secrets management

Environment variables injected via the platform's secrets store (not committed, not baked into
images). `.env.example` in the repo documents every required variable with a placeholder and a
one-line description — no real secret ever exists in the repo, including in git history (checked
via a pre-commit secret-scan hook).

### Auth configuration (see `10-AUTH-AND-ACCOUNTS.md`)

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs/verifies PolicyIQ-issued access tokens |
| `JWT_ACCESS_TTL` | Access token lifetime |
| `JWT_REFRESH_TTL` | Refresh token lifetime |
| `ENTRA_TENANT_ID` | Microsoft tenant for Entra SSO |
| `ENTRA_CLIENT_ID` | PolicyIQ's Entra app registration client ID |
| `ENTRA_CLIENT_SECRET` | Entra app registration secret |
| `ENTRA_REDIRECT_URI` | Must match the callback URL registered with Entra |

### CORS

| Variable | Purpose |
|---|---|
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins (implemented — see `backend/app/main.py`). Defaults to the local dev server, the GitHub Pages mockup origin, and `null` (for local `file://` testing) so `?live=1` in `11-DATA-CONNECTION.md` works without extra setup. Not auth-specific — needed regardless of login method, since it's what lets a cross-origin browser request reach the API at all. |

Implies new backend dependencies for the implementation slice that builds this (not added yet,
this is a docs-only pass): a JWT library (`python-jose` or `pyjwt`), `argon2-cffi` for password
hashing, an OIDC client (`msal` or `authlib`) for the Entra flow, and a `redis` client for
refresh-token storage — reusing the Redis instance already required for rate limiting rather than
adding a second cache dependency.

## Backups

- Postgres: daily automated snapshot + point-in-time recovery via the managed provider,
  retained 30 days.
- R2: versioning enabled on the bucket (documents are already immutable/content-addressed per
  the crawler strategy, so this is a safety net, not the primary durability mechanism).
- Quarterly restore drill: actually restore a snapshot to a scratch environment and verify the
  app boots against it — an untested backup is not a backup.

## Observability (new — not in the original brief)

- Structured JSON logging (request ID propagated from API through Celery tasks) shipped to a
  log aggregator.
- Metrics: crawl success rate per insurer, extraction confidence distribution, citation-
  verification pass rate, `insufficient_evidence` rate, LLM spend per day (budget alert if daily
  spend exceeds a threshold — see extraction strategy's change-triggered re-extraction as the
  primary cost control).
- Alerting: 3+ consecutive crawl failures on an insurer, extraction queue depth growing
  unbounded, LLM error rate spike, budget threshold breach.

## Rollback

Every production deploy is a tagged image; rollback is redeploying the previous tag. Because
migrations are additive-first, rolling back code doesn't require rolling back schema in the
common case.
