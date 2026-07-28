# Technical Architecture

This reflects the resequencing in `00-CHALLENGE.md`: same long-term shape as the original
brief, tightened stack, compliance boundary made explicit at the API layer rather than bolted
on later.

## Design principles

1. **Product-type agnostic core.** `Product` has a `vertical` (insurance, mortgage, kiwisaver,
   ...) and a `product_type` (contents, travel, health, home-loan, ...). Every table below
   (`Section`, `Benefit`, `Exclusion`, `Limit`, ...) hangs off `PolicyVersion`, not off
   insurance-specific fields, so mortgages/KiwiSaver/credit cards reuse the same schema and
   pipeline in later phases — no vertical-specific tables until a vertical proves it needs one.
2. **Every fact is provenance-first.** No row in an extracted-fact table exists without a
   `document_id`, `page`, `paragraph_ref`, and `confidence`. The API never returns a claim it
   can't point at.
3. **Fail closed, not open.** Low-confidence extraction, failed citation verification, or empty
   retrieval all resolve to "insufficient evidence" responses, never a best-guess answer.
4. **One primary vendor per capability, one documented failover.** Not three-way redundancy by
   default (see challenge doc #3). Every external AI call goes through an internal adapter
   interface so the primary/failover choice is a config change.

## Service map

```
┌─────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
│  Crawler     │──▶│  Downloader/ │──▶│  Extraction    │──▶│  Structured   │
│  (Celery)    │   │  Version     │   │  Pipeline      │   │  DB (Postgres)│
│              │   │  Detector    │   │  (OCR + LLM)   │   │               │
└─────────────┘   └──────────────┘   └───────┬────────┘   └──────┬────────┘
                                              │                    │
                                              ▼                    ▼
                                      ┌───────────────┐    ┌───────────────┐
                                      │  Embedding     │───▶│  pgvector      │
                                      │  Worker        │    │  Store         │
                                      └───────────────┘    └──────┬────────┘
                                                                    │
      ┌─────────────────────────────────────────────────────────┘
      ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Query Engine  │──▶│  FastAPI REST │──▶│  Vue 3 SPA     │
│  (retrieval +  │   │  (auth, rate  │   │  (dashboard,   │
│  LLM answer +  │   │  limit, RBAC) │   │  search,       │
│  citation      │   │               │   │  compare...)   │
│  verification) │   │               │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
```

All workers (crawler, downloader, extraction, embedding) are Celery tasks on Redis, independently
scalable, independently retryable. Nothing in the pipeline blocks on another stage synchronously
— a slow OCR job doesn't stall the crawler.

## Repository layout

```
backend/            FastAPI app: routers, auth, RBAC, rate limiting, OpenAPI
  api/               route modules (search, compare, policy, insurer, document, changes, admin)
  core/              settings, security, dependency wiring
  domain/            pydantic models shared with workers via `shared/`
workers/
  crawler/           discovery + scheduling (Celery beat)
  downloader/        fetch, hash/ETag/Last-Modified diffing, R2 upload, version rows
  extractor/         OCR routing (PyMuPDF fast path / Docling structured path) + LLM extraction
  embeddings/         chunker + embedding calls + pgvector writes
  changedetect/       diff PolicyVersions, generate change summaries
shared/              pydantic schemas, DB models (SQLAlchemy), provider adapters (LLM/OCR),
                     citation-verification utility used by both extractor and query engine
database/            Alembic migrations
storage/             R2 client, document key scheme, retention policy
frontend/            Vue 3 + Vite + TS + Tailwind
docker/              Dockerfiles per service, docker-compose.yml, compose.prod.yml
tests/               unit/, integration/, crawler/, extraction/, api/, frontend/
```

## Compliance boundary (new — not in original brief)

A `RESPONSE_MODE` concept sits in the query engine:
- `informational` (default, Phase 1): answers are always framed as "Document X states...",
  always carry citations, never contain second-person recommendations ("you should..."). This
  is what search/compare ship with.
- `advisory` (Phase 2+, feature-flagged off until legal sign-off): would allow personalized
  recommendation/gap-analysis language. Gated at the API layer by a feature flag that requires
  a licensing decision to flip, not just a code change — this is deliberate friction.

## Provider adapters

`shared/providers/llm.py` and `shared/providers/ocr.py` define a single interface
(`extract()`, `answer()`, `embed()`) with a primary implementation and a `FAILOVER_PROVIDER`
env var. Extraction and query-answering code never import a vendor SDK directly — this is what
makes "swap providers" a config change instead of a migration project, and is what makes the
Phase-2 return to multi-provider (if the eval data justifies it) cheap.

## Frontend

Vue 3 + TypeScript + Tailwind + Vite, per the brief. Pages: Dashboard, Search, Compare,
Insurers, Policies, Recent Changes, Document Explorer, Admin. Dark mode via a token-based theme
(see the UI design mockup delivered alongside this doc). One addition to the brief: every
answer/comparison surface renders a **citation chip** (document · page · paragraph · confidence)
as a first-class, always-visible UI element — this is the product's core trust mechanism, not
a tooltip.

## Multi-tenancy / auth

Phase 1: single shared corpus (there's one NZ insurance dataset, not per-tenant data), but
per-user RBAC: `consumer`, `broker`, `admin`. JWT auth, refresh tokens, audit log on every
write and every admin action. Billing/subscription tiers are Phase 2 (see roadmap) — Phase 1
users are invited/beta, not self-serve paying customers, so we're not building a commerce layer
against an unproven extraction pipeline.

## Extensibility for future verticals

Adding mortgages in Phase 2 means: a new `vertical` value, a new insurer-registry-equivalent
(lender registry), and vertical-specific extraction prompts — the crawler, downloader, OCR
routing, embedding pipeline, query engine, comparison engine, and most of the frontend are
unchanged. This is the actual test of "modular architecture," not a claim in a doc: nothing
insurance-specific should exist below the extraction-prompt layer.
