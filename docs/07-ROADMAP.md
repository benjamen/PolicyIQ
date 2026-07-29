# 12-Week Roadmap (Phase 1: NZ Insurance, informational mode only)

Scope, per challenge doc #4: **6 insurers, house/contents + travel only** (no health/life —
gated behind the compliance decision in `00-CHALLENGE.md` #1). No billing/multi-tenant commerce
layer. Every phase ships tested, nothing carries "finish later" debt into the next phase.

**Insurer set:** AA Insurance, AMI, State, Tower, NZI, Vero — six major, well-documented
general insurers, enough to make comparison genuinely useful, small enough to get extraction
quality right before scaling the registry.

## Weeks 1–2 — Foundations
- Repo scaffolding: backend/frontend/workers/shared skeletons, Docker Compose, CI pipeline
  (lint + test, empty test suite passing).
- DB schema + Alembic migrations for the ERD (`02-DATABASE-ERD.md`).
- Provider adapter interfaces (LLM, OCR) with a mock/fake implementation so downstream work
  isn't blocked on vendor keys.
- Insurer registry seeded (6 insurers), crawl-policy config + robots.txt compliance check
  implemented and tested against real robots.txt files for the 6 insurers.
- **Exit test:** CI green on an empty-but-structured codebase; `insurer` rows queryable via API.

## Weeks 3–4 — Crawler & ingestion
- Discovery pipeline (sitemap + Playwright fallback + PDF link extraction) for the 6 insurers.
- Downloader: hash/ETag/Last-Modified diffing, R2 upload, `Document`/`PolicyVersion` creation,
  dedup via hash + first-page similarity.
- Admin crawler-status endpoint + minimal UI.
- **Exit test:** real crawl run against all 6 insurers produces correct, deduped `Document`
  rows with no duplicates on a re-run; failures logged and visible in admin.

## Weeks 5–6 — Extraction pipeline
- OCR routing (PyMuPDF fast path / Docling structured path).
- Section detection + structured extraction (benefits/limits/exclusions/waiting
  periods/definitions/optional covers) with schema validation + retry.
- Gold-set construction begins in parallel (hand-label ~50 claims per insurer as documents come
  in) — this is on the critical path for week 7's eval gate, not a nice-to-have.
- **Exit test:** extraction eval harness runs in CI against the growing gold set; confidence
  scores present on every extracted fact.

## Weeks 7–8 — Citation verification, embeddings, query engine
- Chunking (section-bound, table-safe) + embedding worker + pgvector writes.
- Citation-verification mechanism (`ANSWER_CITATION.verified`).
- Query engine: retrieval → rerank → grounded answer → verification → `insufficient_evidence`
  fallback.
- **Exit test:** eval harness includes retrieval/answer precision, not just extraction; a
  deliberately out-of-corpus question returns `insufficient_evidence`, not a guess.

## Weeks 9–10 — Comparison engine, change detection, API completion
- `/compare` endpoint + diff logic (missing benefits, exclusion differences, limit deltas,
  waiting periods) + PDF/Excel/Markdown export.
- Change-detection worker (section-level diff, `ChangeEvent` generation, summaries) wired to
  the daily crawl.
- Full REST API per `03-API-SPEC.md`, auth + RBAC + rate limiting, OpenAPI published.
- **Exit test:** full API integration suite green; a manually-triggered document update
  produces a correct `ChangeEvent` end to end.

## Weeks 11–12 — Frontend, admin, hardening, launch
- Vue 3 frontend: Dashboard, Search, Compare, Insurers, Policies, Recent Changes, Document
  Explorer, Admin — built against the UI design system delivered this session, dark mode
  included from the start (not retrofitted).
- Security pass: JWT/RBAC review, audit logging on all writes, dependency scan, secrets audit.
- Load/perf pass on search & compare (the LLM-backed, highest-cost endpoints).
- Beta launch to a small invited user group (consumer + broker roles) — not public self-serve
  yet.
- **Exit test:** full test suite (unit/integration/crawler/extraction/frontend/API) green in
  CI; `insufficient_evidence` rate and citation-verification pass rate visible on a live
  dashboard before the first real user question is answered.

## Explicitly deferred past week 12 (not forgotten, sequenced)

| Deferred | Why |
|---|---|
| Health/life insurers (Southern Cross, nib, AIA, Partners Life, Fidelity Life, Accuro, UniMed) | Highest advice-adjacent regulatory risk — needs #1's compliance review first |
| Recommendation engine, gap analysis, claim probability estimator | Advisory-mode features, gated behind FAP licensing decision |
| Billing/subscription/self-serve signup | Don't monetize an unproven extraction pipeline first |
| Broker portal, consumer portal (as distinct experiences), affiliate tracking | Product-persona decisions worth the founder's input before building |
| Live quote automation / Playwright quote engine | Materially different (transactional, not informational) risk profile |
| Mortgages, KiwiSaver, credit cards, utilities, broadband, investment products | Architecture supports them (see `01-ARCHITECTURE.md`); build after Phase 1 insurance proves the pipeline's accuracy |
| MinerU, third LLM provider for true multi-provider redundancy | Add only if eval data on the 6-insurer set shows a concrete gap Docling/primary-LLM can't cover |
