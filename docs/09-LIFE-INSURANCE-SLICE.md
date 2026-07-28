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
| `backend/app/api/v1/compare.py` | `POST /api/v1/compare/life` - grades and ranks products for given filters |
| `backend/app/fixtures/sample_data.py` | **Synthetic** placeholder data (see below) |
| `workers/crawler/policyiq_crawler/` | Scrapy project: generic discovery spider driven by the insurer registry, doc-type classifier, robots.txt-obeying settings |
| UI mockup (Artifact, `docs/08-UI-DESIGN.md`) | Compare view now has a Life Insurance / General Insurance mode toggle; Life mode has the age/smoker/occupation/product-type filter bar and graded score cards |

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

## Why the fixture data uses fake insurer names

`backend/app/fixtures/sample_data.py` exists to exercise the API/grading pipeline before the
crawler and extractor are wired together for real. It uses "Insurer Alpha/Beta/Gamma," not real
company names - attaching invented specific policy terms to a real insurer's name is exactly the
unsourced-claim problem this platform exists to prevent, and a development fixture isn't an
exemption. `CompareResponse.data_source` is set to `"synthetic_fixture"` so no caller can mistake
this for real, verified data. The UI mockup follows the same convention. This module gets deleted
once the repository layer can hydrate real `ProductProfile`s from `graded_fact`/`eligibility_rule`
rows populated by an actual crawl + extraction run.

## What's verified in this session

- `backend`: 16 tests pass (`pytest`) - grading engine unit tests + FastAPI integration tests
  (`TestClient`), including a test that a missing fact lowers `data_completeness` without being
  scored as a failure.
- Alembic migration generated, applied to a throwaway SQLite DB, and confirmed to create all six
  tables correctly.
- `workers/crawler`: 7 tests pass - doc-type classifier (including a bug the tests caught: URL
  separators like `-`/`_`/`/` weren't normalized before keyword matching, so
  `policy-wording.pdf` didn't match `"policy wording"`; fixed in `doctype.py`) + registry
  integrity checks (no duplicate insurer names/domains, every seed has a positive crawl delay).
- `scrapy list` confirms the spider registers and loads without hitting any real insurer site -
  no live crawl was run against a production insurer in this session (see robots.txt note above).
- UI mockup changes screenshotted via headless Chromium in both themes - caught and fixed a real
  CSS stacking bug (the grade-ring score number was rendering behind the donut cutout because an
  absolutely-positioned `::before` was painting above non-positioned inline text; fixed by making
  the score text itself a positioned sibling so it paints on top).

## Not built yet

- The Downloader worker (fetch/hash/version/R2-upload) and the extraction pipeline that would
  turn crawled PDFs into real `graded_fact`/`eligibility_rule` rows - this slice stops at
  discovery + a synthetic-data-backed API/UI, per `07-ROADMAP.md`'s weeks 3-8 sequencing.
- A repository layer translating `PolicyVersion` + `GradedFact` + `EligibilityRule` rows into
  `ProductProfile` objects - straightforward once real data exists, deliberately not built
  against fixtures that would need throwing away.
- Occupation-category normalization across insurers (each insurer's own labels vs. our
  normalized `code`) - `OccupationCategory.insurer_label` exists in the schema for this but the
  actual mapping needs real extracted data to build against.
