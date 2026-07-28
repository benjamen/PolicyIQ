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
