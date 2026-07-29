# Vertical Slice: Life Insurance Comparison (Age / Smoker / Occupation)

First working slice of the platform: scrape → structured store → graded comparison UI, for the
use case "enter age, smoker status, occupation category, product type → compare and grade life
insurance products." Scoped per the decisions made when this was picked up:

- **Document-derived only, no live premium quoting.** Age/smoker/occupation filter *eligibility*
  and surface *policy structure*; they never produce a $ premium. This keeps the platform in the
  "informational" compliance mode from `01-ARCHITECTURE.md` and out of quote-comparison-site
  territory (which the original brief explicitly ruled out, and which pushes harder into FMA/FAP
  advice risk - see `00-CHALLENGE.md` #1).
- **Grading is deterministic, not a second LLM call.** Once a fact is extracted and citation-
  verified, turning it into a comparable score is a plain function of that fact. This keeps a
  grade auditable ("why did this get 74/100" is answerable from weights + facts) and adds no
  extra hallucination surface on top of extraction.

## What's built

| Path | What |
|---|---|
| `backend/app/domain/models.py` | Vocabulary shared by the grading engine, DB, and API: `ProductProfile`, `TpdDefinition`, `OccupationRestriction`, `PremiumStructure`, `SourceRef` (every fact carries page/paragraph/confidence) |
| `backend/app/services/grading.py` | The grading engine: eligibility check (age/smoker/occupation-exclusion) + six weighted, sourced criteria (see below) |
| `backend/app/db/models.py` | SQLAlchemy schema extension: `occupation_category`, `eligibility_rule`, `graded_fact`, on top of thin `insurer`/`product`/`policy_version` stand-ins |
| `backend/alembic/` | Migration for the above, verified against a throwaway SQLite DB (see "What's verified" below) |
| `backend/app/api/v1/compare.py` | `POST /api/v1/compare/life` - loads real `ProductProfile`s via the repository layer, grades and ranks them for given filters |
| `backend/app/db/repository.py` | `load_product_profiles()` - hydrates `ProductProfile`s from `GradedFact`/`EligibilityRule` rows for the current `PolicyVersion` of each product; fail-closed (excludes versions with no general eligibility rule, returns `[]` rather than falling back to anything synthetic) |
| `backend/app/storage/` | `StorageAdapter` Protocol + `LocalDiskStorage`; content-addressed key scheme (`{insurer}/{product_type}/{doc_type}/{sha256[:12]}-{filename}`) |
| `backend/app/pipeline/downloader.py` | `download_and_version()` - HEAD-first ETag/Last-Modified diffing, sha256 hash-dedup across URLs, storage + `Document` row + `PolicyVersion` bump |
| `backend/app/ocr/` | `route_ocr()` - PyMuPDF native-text extraction first (95% page-coverage threshold), Docling structured/scanned fallback |
| `backend/app/providers/llm.py` | `LLMProvider` Protocol, `MockLLMProvider`, Pydantic extraction schema (`SectionExtraction` + per-table sub-models), `extract_with_retry()` |
| `backend/app/verification.py` | `verify_citation()` - the "never hallucinate" gate: exact-substring then fuzzy (`difflib`) match of every claimed `source_quote` against the section's own parsed text; unverified facts are rejected, never persisted |
| `backend/app/pipeline/sections.py`, `backend/app/pipeline/extraction.py` | `build_sections()` (one `Section` per PDF page, Phase-1) + `process_section()` (calls the LLM provider, verifies every fact, persists only verified ones) |
| `backend/app/pipeline/run_ingest.py` | CLI tying it together: crawler JSONL → downloader → OCR → sections → extraction, for one insurer's crawl output |
| `backend/app/db/seed_insurers.py` | Seeds the 7 real `LIFE_INSURER_SEED` insurers into `Insurer` rows, insert-only/idempotent |
| `workers/crawler/policyiq_crawler/` | Scrapy project: generic discovery spider driven by the insurer registry, doc-type classifier, robots.txt-obeying settings |
| UI mockup (Artifact, `docs/08-UI-DESIGN.md`) | Compare view now has a Life Insurance / General Insurance mode toggle; Life mode has the age/smoker/occupation/product-type filter bar and graded score cards; live `?live=1` mode fetches the real deployed API |

## Grading criteria

Six weighted criteria, each excluded from the average (not zeroed) when the underlying fact
hasn't been extracted yet - `data_completeness` on the response makes this visible instead of
silently blending "bad" and "unknown":

| Criterion | Weight | What's compared |
|---|---|---|
| TPD definition | 25% | Own-occupation > modified own-occupation > any-occupation > ADL basis |
| Trauma/critical-illness condition count | 20% | Normalized against an estimated 15-50 condition market range - revisit once the gold eval set gives real observed bounds |
| Occupation restriction | 20% | None found > loading > exclusion, for the caller's specific occupation category |
| Premium structure | 15% | Level > stepped; guaranteed > reviewable |
| Waiver of premium | 10% | Included vs not |
| Automatic benefits count | 10% | Normalized against a 10-benefit ceiling |

Eligibility (age window, smoker-status availability, occupation exclusion) is checked
separately and ineligible products are still returned, not hidden - hiding a disqualified
product without showing why would itself be an unsourced claim.

## Insurer registry - grounded, not guessed

The market research done before seeding this (see PR discussion) surfaced two things worth
recording: RBNZ, not the FMA, maintains the authoritative public register of licensed insurers
in NZ (84 entities, all insurance lines, under the Insurance (Prudential Supervision) Act 2010);
and several names that surface in a "top life insurers" web search are aggregators/brokers
(LifeDirect, Glimp, Compare.org.nz), not insurers, and don't belong in a document-source
registry. `workers/crawler/policyiq_crawler/registry.py` seeds the real major underwriters (AIA,
Partners Life, Fidelity Life, Asteron Life, Chubb Life, MAS, Pinnacle Life) and documents
`discover_insurers()` as the place RBNZ-register cross-referencing gets wired in later to grow
the set mechanically instead of by further hand-curation - matching the "consistently" scrape
requirement better than a hand-maintained top-N list would.

robots.txt could not be fetched live for these insurers from this development sandbox (outbound
requests returned 403 at the network proxy - an environment restriction, not a finding about the
sites). `ROBOTSTXT_OBEY = True` in `settings.py` is the actual enforcement mechanism, checked
fresh at crawl time from a real deployment environment.

## Why the live API currently returns empty results

`backend/app/fixtures/sample_data.py` (synthetic "Insurer Alpha/Beta/Gamma" placeholder data) has
been **deleted**. It existed only to exercise the API/grading pipeline before the real pipeline
existed - attaching invented specific policy terms to a real insurer's name would have been
exactly the unsourced-claim problem this platform exists to prevent, so once the repository layer
could hydrate real `ProductProfile`s from `graded_fact`/`eligibility_rule` rows, the fixture's own
docstring called for its deletion rather than being kept as a permanent fallback.

`CompareResponse.data_source` is now a closed enum (`synthetic_fixture` | `extracted_verified`,
`backend/app/schemas/compare.py`) and `compare.py` always returns `extracted_verified` - there is
no code path left that can emit fixture data. Consequence: until a real crawl + download +
extraction run has populated the database, `POST /api/v1/compare/life` returns
`{"results": [], "data_source": "extracted_verified"}` - an honest empty state, not an error and
not a silent fallback to fake data. This is deliberate, matching `01-ARCHITECTURE.md` principle
#3 (fail closed, never guess).

## What's verified in this session

- `backend`: 52 tests pass, 1 explicitly skipped (`pytest`) - grading engine, FastAPI
  integration, storage, OCR routing, LLM provider adapter + retry logic, citation verification,
  downloader, repository layer, insurer seed script, migration round-trip, and a fully offline
  end-to-end test (`tests/pipeline/test_e2e.py`) that builds a synthetic PDF, routes it through
  OCR, extracts it with `MockLLMProvider`, verifies citations (including proving a deliberately
  fabricated quote gets rejected, not persisted), hydrates it via the repository layer, grades it,
  and asserts the result through a real `TestClient(app)` HTTP call. The skipped test exercises
  real Docling against Hugging Face Hub and needs network this sandbox's proxy blocks by policy -
  it's designed to be run manually, not part of the default suite.
- Alembic migration chain (including the pipeline-schema migration) applied to a throwaway SQLite
  DB, confirmed to create every table/FK, and round-trips clean on downgrade/upgrade.
- `workers/crawler`: 7 tests pass - doc-type classifier (including a bug the tests caught: URL
  separators like `-`/`_`/`/` weren't normalized before keyword matching, so
  `policy-wording.pdf` didn't match `"policy wording"`; fixed in `doctype.py`) + registry
  integrity checks (no duplicate insurer names/domains, every seed has a positive crawl delay).
- `scrapy list` confirms the spider registers and loads without hitting any real insurer site -
  no live crawl was run against a production insurer in this session (see robots.txt note above,
  and the network-sandbox note below).
- UI mockup changes screenshotted via headless Chromium in both themes - caught and fixed a real
  CSS stacking bug (the grade-ring score number was rendering behind the donut cutout because an
  absolutely-positioned `::before` was painting above non-positioned inline text; fixed by making
  the score text itself a positioned sibling so it paints on top).
- The deployed backend (`api.policyiq.nz`) confirmed live over real TLS; `POST /api/v1/compare/life`
  returns the honest empty-results response described above rather than erroring, since no real
  crawl has been run against it yet.

## Not built yet

- **A real `LLMProvider` implementation.** `app/providers/llm.py`'s Protocol, retry logic, and
  Pydantic extraction schema are built and tested against `MockLLMProvider`; no real
  Groq/OpenAI/etc. adapter exists yet. `run_ingest.py` runs download + OCR + section-building
  against real documents but explicitly skips extraction (reports it, doesn't fake it) until a
  real provider is wired in - it will never run the mock against arbitrary real document text.
- **A real crawl.** No live crawl has been run against a production insurer site from this
  session's development sandbox (network egress here is policy-restricted to an allowlist - see
  `06-DEPLOYMENT-PLAN.md`). The project's VPS (already hosting the live backend, unrestricted
  outbound access) is the realistic place to run `scrapy crawl policy_documents -o
  discovered/<insurer>.jsonl` for real, then feed the output into `run_ingest.py` - an ops step,
  not a code gap.
- Occupation-category normalization across insurers (each insurer's own labels vs. our
  normalized `code`) - `OccupationCategory.insurer_label` exists in the schema for this but the
  actual mapping needs real extracted data to build against.
- Real Docling invocation is untested in this sandbox (blocked by the same network restriction);
  the routing decision itself (`route_ocr()` falling through from native-text to structured) is
  tested with fake backends, but the real Docling call has only ever run against a manufactured
  low-coverage PDF locally, not verified in CI.
