# Comprehensive Data Scraping Architecture

## Vision

A fully automated, weekly-refreshed insurance intelligence database that maintains complete,
citation-verified, comparable coverage across all NZ insurance providers, their products,
the risk events they cover, the risk areas they operate in, and every document they publish
(policy wordings, brochures, PDS documents, claims guides).

This extends the existing pipeline (docs/04-CRAWLER-STRATEGY.md) from a manual CLI workflow
to a production-grade, self-healing, scheduled system — without losing the fail-closed,
provenance-first principles established in docs/01-ARCHITECTURE.md.

---

## 1. Extended Data Model

The existing ERD (docs/02-DATABASE-ERD.md) covers documents, sections, and extracted facts.
This architecture adds three new first-class dimensions that make cross-insurer comparison
structurally complete rather than dependent on free-text matching:

### 1.1 Risk Area (taxonomy of what insurance covers)

```
RISK_AREA
  id            UUID PK
  code          VARCHAR(60) UNIQUE    -- "natural_disaster", "theft", "liability", "medical"
  name          VARCHAR(200)          -- "Natural Disaster / Catastrophe"
  parent_id     UUID FK(RISK_AREA)   -- nullable, for hierarchy (property > flood > river_flood)
  description   TEXT
  sort_order    INT
```

A curated, human-maintained taxonomy (like nz_insurer_catalog.py — static, not scraped).
Examples:

- Property Damage > Fire, Flood, Earthquake, Storm, Landslip, Retaining Wall Collapse
- Liability > Public Liability, Professional Indemnity, Employer Liability
- Personal > Death, TPD, Trauma/Critical Illness, Income Loss
- Medical > Surgical, Diagnostic, Cancer Treatment, Mental Health
- Motor > Collision, Theft, Third-Party Damage, Windscreen
- Travel > Medical Overseas, Cancellation, Baggage Loss, Rental Vehicle Excess

### 1.2 Risk Event (a specific covered/uncovered scenario per product)

```
RISK_EVENT
  id                UUID PK
  risk_area_id      UUID FK(RISK_AREA)
  policy_version_id UUID FK(POLICY_VERSION)
  name              VARCHAR(300)       -- "Retaining wall collapse due to natural erosion"
  coverage_status   VARCHAR(20)        -- covered | excluded | limited | sub_limited | silent
  detail            TEXT               -- extracted description of how this event is treated
  monetary_limit    NUMERIC(12,2)      -- nullable, the cap if limited
  percentage_limit  NUMERIC(5,2)       -- nullable
  excess_amount     NUMERIC(12,2)      -- nullable, the excess/deductible
  waiting_period_days INT              -- nullable
  document_id       UUID FK(DOCUMENT)
  section_id        UUID FK(SECTION)
  page              INT
  paragraph_ref     VARCHAR(40)
  confidence        FLOAT
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ
```

This is the **comparison primitive**: "for risk event X, what does each insurer do?"
Today this comparison requires free-text matching across Benefit/Limit/Exclusion rows.
RiskEvent makes it a first-class, queryable, groupable fact.

coverage_status semantics:
- `covered`: explicitly included, no special limitation beyond standard excess
- `excluded`: explicitly stated as not covered
- `limited`: covered but with a monetary or percentage cap below the general sum insured
- `sub_limited`: a specific sub-limit carved out within a broader benefit
- `silent`: the document neither includes nor excludes it (important — not the same as excluded)

### 1.3 Document Collection (brochures, marketing, supplementary)

```
DOCUMENT_COLLECTION
  id                UUID PK
  policy_version_id UUID FK(POLICY_VERSION)
  collection_type   VARCHAR(40)   -- brochure | pds | wording | claims_guide | schedule | marketing
  title             VARCHAR(400)
  source_url        TEXT
  storage_key       TEXT
  sha256_hash       CHAR(64)
  mime_type         VARCHAR(60)
  page_count        INT
  published_date    DATE           -- nullable, from document metadata or content
  effective_date    DATE           -- nullable, when this version takes effect
  superseded_by_id  UUID FK(DOCUMENT_COLLECTION) -- nullable, forms a version chain
  etag              TEXT
  last_modified     TEXT
  fetched_at        TIMESTAMPTZ
  is_current        BOOLEAN DEFAULT TRUE

BROCHURE_ASSET
  id                    UUID PK
  document_collection_id UUID FK(DOCUMENT_COLLECTION)
  asset_type            VARCHAR(40)  -- cover_image | diagram | table | infographic
  storage_key           TEXT
  page_number           INT
  caption               TEXT         -- nullable, OCR-extracted caption
  width_px              INT
  height_px             INT
```

The existing `Document` table tracks policy wordings/PDS through the extraction pipeline.
`DOCUMENT_COLLECTION` is a broader catalog that also captures brochures, marketing PDFs,
product schedules, and visual assets — things that inform comparison but don't go through
LLM extraction (they're reference material, not fact sources).

### 1.4 Coverage Matrix (materialized comparison view)

```
COVERAGE_MATRIX (materialized view, refreshed weekly)
  insurer_id        UUID
  insurer_name      TEXT
  product_type      VARCHAR(60)
  risk_area_id      UUID
  risk_area_name    TEXT
  risk_event_name   TEXT
  coverage_status   VARCHAR(20)
  monetary_limit    NUMERIC
  excess_amount     NUMERIC
  document_id       UUID
  page              INT
  confidence        FLOAT
  last_verified_at  TIMESTAMPTZ
```

A denormalized, pre-joined view that powers the comparison UI directly — "show me every
insurer's position on flood damage for house insurance" becomes a single indexed query
instead of a 5-table join computed on every request.

### 1.5 Pipeline Run Tracking

```
PIPELINE_RUN
  id              UUID PK
  run_type        VARCHAR(40)    -- scheduled_weekly | manual | backfill | retry
  insurer_id      UUID FK(INSURER) -- nullable, NULL = all-insurer run
  status          VARCHAR(20)    -- pending | running | completed | failed | partial
  started_at      TIMESTAMPTZ
  completed_at    TIMESTAMPTZ
  stats_json      JSONB          -- {documents_seen, downloaded, unchanged, failed, sections, extractions}
  error_summary   TEXT
  triggered_by    VARCHAR(60)    -- scheduler | admin:<email> | ci

EXTRACTION_QUALITY_METRIC
  id              UUID PK
  pipeline_run_id UUID FK(PIPELINE_RUN)
  insurer_id      UUID FK(INSURER)
  total_facts_extracted   INT
  facts_verified          INT
  facts_rejected          INT
  verification_rate       FLOAT   -- verified / total
  avg_confidence          FLOAT
  low_confidence_count    INT     -- facts below 0.7 threshold
  model_used              VARCHAR(100)
  duration_seconds        FLOAT
```

---

## 2. Pipeline Architecture

### 2.1 System Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCHEDULER (cron / APScheduler)                    │
│  Weekly: Mon 02:00 NZST, staggered per-insurer (2-min intervals)        │
│  Daily:  Health check + change-detection scan (HEAD requests only)      │
│  Ad-hoc: Admin-triggered single-insurer re-crawl                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ enqueues
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     TASK QUEUE (Redis + ARQ / Celery)                    │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Discover │→ │ Download │→ │   OCR    │→ │ Extract  │→ │ Verify  │ │
│  │  Worker  │  │  Worker  │  │  Worker  │  │  Worker  │  │ Worker  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│       │              │             │              │             │       │
│       ▼              ▼             ▼              ▼             ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Brochure │  │ Version  │  │ Section  │  │  Risk    │  │Coverage │ │
│  │ Collector│  │ Detector │  │ Builder  │  │  Event   │  │ Matrix  │ │
│  │          │  │          │  │          │  │ Mapper   │  │ Refresh │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA STORES                                     │
│                                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL │  │   pgvector │  │  R2/S3     │  │  Redis           │  │
│  │ (primary)  │  │ (embeddings│  │ (documents │  │  (queue + cache) │  │
│  │            │  │  + search) │  │  + assets) │  │                  │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY                                      │
│  Structured logging (JSON) → Pipeline dashboard → Alerting              │
│  EXTRACTION_QUALITY_METRIC per run → Regression detection               │
│  3-strike failure auto-disable → Admin notification                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Stage Details

#### Stage 1: Discovery (per insurer, weekly)

Input: InsurerSeed from registry.py
Output: DiscoveredDocumentItem rows (JSONL + DB staging table)

- Sitemap.xml fetch (fast path)
- Link-following crawl with Playwright fallback (existing spider)
- Document hub path seeding (existing)
- **NEW**: Brochure/marketing asset discovery (follow "Download brochure", "Product guide" links)
- **NEW**: RSS/Atom feed check for document update announcements
- **NEW**: robots.txt re-validation before each run (insurers change this)
- Classification: doc_type + in_scope flag (existing)
- **NEW**: effective_date extraction from URL patterns and link text ("effective 1 March 2026")

Rate limiting: per-insurer CrawlPolicy (existing), plus global concurrency cap
(max 3 insurers crawling simultaneously, never parallel against the same domain).

#### Stage 2: Download & Version Detection

Input: DiscoveredDocumentItem queue
Output: Document rows + stored files + version chain updates

- HEAD-first diffing (ETag/Last-Modified) — existing
- SHA-256 content addressing — existing
- **NEW**: Supersedes chain — when a new version is detected, the old Document's
  PolicyVersion gets status="superseded", new one gets status="current"
- **NEW**: Brochure/asset download into DOCUMENT_COLLECTION (separate from extraction pipeline)
- **NEW**: Binary asset extraction from PDFs (cover images, diagrams) into BROCHURE_ASSET
- **NEW**: MIME validation (reject non-PDF/non-image responses that slipped through discovery)
- Storage: R2 in production, local disk in dev (existing adapter pattern)

#### Stage 3: OCR & Section Building

Input: Document content bytes
Output: ParsedDocument + Section rows

- PyMuPDF fast path for native-text PDFs — existing
- Docling structured path for complex/scanned layouts — existing
- **NEW**: Timeout escalation (120s → 300s → 600s with admin alert at each tier)
- **NEW**: OCR quality scoring (character density per page — flag pages with <50 chars
  as likely-image-only, route to Docling or flag for manual review)
- **NEW**: Table detection and structured extraction (Docling's table model)
- Section splitting: one section per logical heading block (existing), with
  page_start/page_end/paragraph_ref coordinates

#### Stage 4: LLM Extraction + Citation Verification

Input: Section text + ParsedDocument
Output: Benefit/Limit/Exclusion/Definition/WaitingPeriod/OptionalBenefit + GradedFact
        + EligibilityRule + RiskEvent rows

- Provider adapter (Groq/NVIDIA) with retry + prompt correction — existing
- Citation verification (exact substring + fuzzy match) — existing
- **NEW**: Risk Event extraction — for each section, identify specific scenarios
  and classify coverage_status (covered/excluded/limited/sub_limited/silent)
- **NEW**: Risk Area mapping — map each extracted fact to the risk taxonomy
  (LLM proposes, deterministic rule validates against the curated taxonomy)
- **NEW**: Cross-section consistency check — if page 3 says "flood excluded"
  and page 12 says "flood covered up to $50,000", flag for review rather than
  persisting contradictory facts
- **NEW**: Extraction diff on re-crawl — only re-extract sections whose text
  actually changed (SHA-256 of section text), not the whole document
- Rejected facts logged with reason (verification failure, schema invalid, low confidence)

#### Stage 5: Post-Processing & Matrix Refresh

Input: All extracted facts for the run
Output: COVERAGE_MATRIX refresh + quality metrics + change events

- **NEW**: Risk Event normalization — deduplicate semantically-identical events
  across sections ("flood damage" = "damage caused by flooding")
- **NEW**: Coverage matrix materialized view refresh
- **NEW**: Change event generation (diff current vs. previous PolicyVersion facts)
- **NEW**: Quality metric computation and regression check
- **NEW**: Embedding generation for new/changed sections (pgvector)
- Alert if verification_rate drops below 85% for any insurer (regression signal)

### 2.3 Scheduling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    WEEKLY SCHEDULE (Monday NZST)                  │
├──────────┬──────────────────────────────────────────────────────┤
│ 02:00    │ Health check: HEAD all known document URLs           │
│ 02:15    │ Group A: AMI, State, NZI (IAG/Suncorp cluster)      │
│ 02:25    │ Group B: Tower, Vero, AA Insurance                   │
│ 02:35    │ Group C: FMG, MAS, Trade Me, Initio                  │
│ 02:45    │ Group D: Life insurers (AIA, Partners, Fidelity...)  │
│ 03:00    │ Group E: Health (Southern Cross, nib, UniMed)        │
│ 03:10    │ Group F: Specialty (SPCA, Cove, 1Cover, PD, etc.)   │
│ 03:30    │ Coverage matrix refresh + embedding generation       │
│ 04:00    │ Quality report generation + regression check         │
│ 04:15    │ Change event digest + admin notification             │
└──────────┴──────────────────────────────────────────────────────┘

Daily (lightweight):
  06:00    HEAD-only scan of all current document URLs
           → if ETag/Last-Modified changed, enqueue immediate re-download
           → catches mid-week document updates without a full crawl

Ad-hoc:
  Admin trigger → single-insurer full pipeline run (any day)
  New insurer onboard → discovery + full extraction (manual trigger)
```

Staggering rationale: insurers sharing a parent company (IAG owns AMI/State/NZI,
Suncorp owns Vero/AA) likely share CDN infrastructure — hitting them in the same
group with 2-minute gaps is polite and avoids looking like a distributed attack.

---

## 3. Data Consistency Guarantees

### 3.1 Transactional Boundaries

- Each document is an atomic unit: download + OCR + section-build + extraction
  either fully commits or fully rolls back (existing pattern in run_ingest.py).
- Coverage matrix refresh is a single transaction: the old matrix stays visible
  until the new one is fully computed (SWAP, not DELETE+INSERT).
- Risk Event mapping uses a deterministic validation step: an LLM-proposed
  risk_area_id that doesn't exist in the curated taxonomy is rejected, not
  silently persisted with a NULL area.

### 3.2 Idempotency

Every pipeline stage is idempotent against re-runs:
- Discovery: same URL discovered twice → deduped by (insurer, document_url)
- Download: same SHA-256 → linked to existing Document, no duplicate row
- Extraction: section text unchanged → skipped (text hash comparison)
- Risk Events: same (policy_version, risk_area, name) → upsert, not insert
- Matrix: full rebuild from source facts, never incremental mutation

### 3.3 Accuracy Verification (multi-layer)

Layer 1 — Mechanical citation verification (existing):
  Every fact's source_quote must appear in the OCR'd page text.

Layer 2 — Cross-document consistency (new):
  When the same insurer publishes both a PDS and a brochure, key facts
  (sum insured, excess amounts) are cross-checked. Discrepancies flagged
  for admin review, not auto-resolved.

Layer 3 — Temporal consistency (new):
  A fact extracted from a 2024 document that contradicts the same fact
  from a 2026 document → the newer document wins, but the contradiction
  is logged as a ChangeEvent (not silently overwritten).

Layer 4 — Gold-set regression (existing design, not yet implemented):
  Hand-labeled eval set (50-100 claims per insurer) run after every
  extraction model/prompt change. Precision/recall must not regress.

Layer 5 — Human review queue (new):
  Facts with confidence < 0.7, contradictory facts, and "silent" coverage
  on common risk events route to an admin review queue. Reviewed facts get
  confidence = 1.0 and a reviewer stamp.

---

## 4. Comparability Architecture

### 4.1 The Comparison Problem

Today: comparing "what does AMI cover for retaining walls?" requires:
1. Find AMI's house PolicyVersion
2. Load all Sections
3. Search Benefit/Limit/Exclusion rows for text matching "retaining wall"
4. Manually interpret coverage_status from the text

With Risk Events: it's a single query:
```sql
SELECT insurer_name, coverage_status, monetary_limit, excess_amount, page, confidence
FROM coverage_matrix
WHERE risk_area_code = 'property_damage'
  AND risk_event_name ILIKE '%retaining wall%'
  AND product_type = 'house'
ORDER BY insurer_name;
```

### 4.2 Normalization Rules

For comparison to work across insurers who use different language:

- **Risk Area taxonomy is curated, not scraped.** A human maintains the
  hierarchy. The LLM maps extracted facts TO the taxonomy, never invents
  new areas.
- **Risk Event names are semi-normalized.** The LLM proposes a canonical
  name ("Retaining wall collapse"), and a fuzzy-match dedup step merges
  near-identical names within the same risk_area ("Retaining wall failure"
  → "Retaining wall collapse"). Admin can override merges.
- **Coverage status is deterministic from extracted facts:**
  - Benefit exists + no Limit on it → "covered"
  - Exclusion exists → "excluded"
  - Benefit + Limit with amount < general sum insured → "limited"
  - Neither benefit nor exclusion mentions it → "silent"
  - This mapping is code, not LLM judgment.

### 4.3 Product Brochure Integration

Brochures serve a different purpose than wordings:
- **Wordings/PDS** → extraction pipeline → structured facts → comparison
- **Brochures** → asset catalog → visual reference → linked from comparison UI

A comparison row for "AMI House Insurance" links to:
- The policy wording (citation source for every fact)
- The current product brochure (visual overview, marketing positioning)
- Any supplementary schedules (optional cover pricing, excess tables)

Brochure assets are NOT fact sources — they're reference material. If a
brochure says "up to $1M cover" but the wording says $750K, the wording
wins (it's the legal contract). The discrepancy is flagged, not hidden.

---

## 5. Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Task Queue | ARQ (Redis-backed) | Lighter than Celery, async-native, fits the existing httpx/async patterns. Celery if team grows. |
| Scheduler | APScheduler (in-process) or cron | Simple weekly schedule doesn't need Airflow/Prefect. Cron on the VPS is fine for Phase 1. |
| Database | PostgreSQL 16 + pgvector | Already specified in architecture. SQLite → Postgres migration is the prerequisite. |
| Object Storage | Cloudflare R2 (production) / local disk (dev) | Existing adapter pattern. R2's free egress suits document-heavy reads. |
| OCR | PyMuPDF (fast) + Docling (structured) | Existing. Add timeout escalation + quality scoring. |
| LLM | Groq (primary) + NVIDIA NIM (failover) | Existing adapter. Add structured output mode for risk event extraction. |
| Embeddings | text-embedding-3-small (OpenAI) or nomic-embed | For pgvector semantic search. Deferred until query engine is built. |
| Monitoring | Structured JSON logs + health endpoint + admin dashboard | No Datadog/Grafana until the team justifies the cost. |
| Frontend | Vue 3 + Vite + TS + Tailwind | The single-file mockup must be rewritten. This architecture assumes it. |

---

## 6. Failure Handling & Self-Healing

### 6.1 Per-Stage Failure Modes

| Stage | Failure | Response |
|-------|---------|----------|
| Discovery | robots.txt disallows | Skip insurer, alert admin, log to PIPELINE_RUN |
| Discovery | Site redesign breaks selectors | 3-strike auto-disable, admin alert with last-good snapshot |
| Discovery | Playwright timeout | Retry once, then skip URL (logged) |
| Download | 403/404 | Mark document as potentially-moved, trigger re-discovery next run |
| Download | Hash mismatch on "unchanged" ETag | Download anyway (CDN cache inconsistency), log anomaly |
| OCR | Timeout (>600s) | Flag document as OCR-blocked, admin review queue |
| OCR | Zero text extracted | Likely image-only scan → route to Docling → if still zero, manual |
| Extraction | LLM rate limit | Exponential backoff, 3 retries, then queue for next run |
| Extraction | Schema validation failure | Retry with correction prompt (existing), then reject + log |
| Extraction | Verification rate < 50% for a document | Halt that document, flag for prompt/model review |
| Matrix | Refresh takes > 5 min | Alert (indicates data volume growth needing optimization) |

### 6.2 Auto-Disable & Recovery

An insurer is auto-disabled after:
- 3 consecutive weekly crawl failures (site may have blocked us)
- Verification rate < 50% for 2 consecutive runs (model/prompt regression)
- Admin manual flag (insurer requested takedown)

Recovery requires admin action:
- Review failure logs
- Fix crawl policy / update selectors / adjust prompt
- Manually re-enable + trigger a test run
- Test run must pass (verification rate > 85%) before rejoining the schedule

---

## 7. Implementation Sequence

### Phase A: Infrastructure (Week 1-2)
1. Migrate SQLite → PostgreSQL (docker-compose, Alembic, connection pooling)
2. Add Redis + ARQ task queue
3. Implement PIPELINE_RUN tracking table
4. Convert run_ingest.py CLI into an ARQ task (same logic, new entrypoint)
5. Add APScheduler weekly trigger

### Phase B: Data Model Extension (Week 2-3)
1. Alembic migration: RISK_AREA, RISK_EVENT, DOCUMENT_COLLECTION, BROCHURE_ASSET
2. Seed the risk area taxonomy (curated, ~80-120 nodes)
3. Extend extraction prompt to emit risk events alongside existing facts
4. Implement risk event → risk area mapping with taxonomy validation
5. Implement coverage_status derivation logic (deterministic, from existing facts)

### Phase C: Brochure & Asset Pipeline (Week 3-4)
1. Extend crawler to discover brochure/marketing PDFs (new doc_type patterns)
2. Implement DOCUMENT_COLLECTION ingestion (download, hash, store, metadata)
3. Implement BROCHURE_ASSET extraction (PyMuPDF image extraction per page)
4. Link brochures to their PolicyVersion in the UI

### Phase D: Automation & Quality (Week 4-5)
1. Weekly scheduler with per-insurer staggering
2. Daily HEAD-only change detection scan
3. EXTRACTION_QUALITY_METRIC computation per run
4. Regression alerting (verification rate drop, new failure patterns)
5. Admin review queue for low-confidence/contradictory facts

### Phase E: Coverage Matrix & Comparison (Week 5-6)
1. COVERAGE_MATRIX materialized view + refresh task
2. New API endpoints: /api/v1/coverage/matrix, /api/v1/risk-areas, /api/v1/risk-events
3. Frontend: risk-area-browsable comparison view
4. Frontend: brochure gallery per product
5. Change event digest (weekly email/admin notification)

---

## 8. Monitoring & Observability

### Pipeline Dashboard (admin view)

- Last successful run per insurer (date, duration, documents processed)
- Current verification rate per insurer (trend line over last 8 weeks)
- Documents pending review (low confidence, contradictory, OCR-blocked)
- Coverage completeness: % of risk areas with at least one extracted fact per insurer
- Next scheduled run countdown

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Verification rate (per insurer) | < 90% | < 75% |
| Consecutive failures | 2 | 3 (auto-disable) |
| OCR timeout rate | > 10% of documents | > 25% |
| Coverage matrix staleness | > 8 days since refresh | > 14 days |
| New "silent" risk events | > 20% increase week-over-week | > 40% |
| LLM extraction cost | > 1.5x previous week | > 2x |

---

## 9. Legal & Compliance (extends docs/04)

- Weekly crawl frequency is conservative (most insurers update quarterly)
- robots.txt re-checked every run (not cached from first crawl)
- Brochure collection follows the same rate-limiting and identification rules
- No document is republished — only short cited excerpts (existing fair-dealing posture)
- Brochure thumbnails (cover images) are low-resolution, attributed, and link back to source
- Takedown process: admin sets insurer.blocked = true → immediate schedule removal +
  existing documents remain indexed internally but stop serving new citations
- The Contracts of Insurance Act 2024 (in force by Nov 2027) may create new disclosure
  obligations — architecture supports a future "regulatory filing" document source type
