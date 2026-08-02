# Competitive Strategy & Plan: Beating Quote Monster

Purpose: capture PolicyIQ's commercial direction and the concrete workstreams to deliver it.
This **extends and partially supersedes** the "informational mode only, no live premium
quoting" scope set in `09-LIFE-INSURANCE-SLICE.md` and `00-CHALLENGE.md` #1 — see the
compliance note in §4 before acting on the pricing workstream.

## 1. Goal

Make PolicyIQ the NZ insurance comparison platform that beats the incumbent adviser tool,
**Quote Monster** (research brand: QPR / Quality Product Research Limited), by:

- Selling the document-grounded **head-to-head feature comparison for a $49/month
  subscription**, undercutting Quote Monster's "Research Monster" tier (>$99).
- Treating **pricing comparison as free table-stakes** (Quote Monster's free "Basic" tier
  already gives quotes and pricing).
- Competing on **verifiable evidence, breadth, and privacy** rather than on opaque scores.

## 2. Competitive landscape

Quote Monster has two tiers:

| Tier | Price | What it gives |
|---|---|---|
| Quote Monster Basic | Free | Insurance quotes and pricing comparisons |
| Research Monster | >$99 | Detailed head-to-head feature reports (heatmaps, scores, exclusions) |

The Research Monster "Head to Head" report format (reviewed from sample PDFs):

- Client banner with **personal information** — name, organisation, and demographics
  (`40 / Male / Non-Smoker / Class 1 / Employed`).
- Two insurers side-by-side with **financial-strength ratings** (e.g. "AA by Fitch",
  "A- by AM Best") and a numeric **Total Score** (e.g. 107.51 vs 107.9).
- Per-criterion **heatmap rows** — Cover Conversion, Special Events Increase, Inflation
  Adjustment, Grief & Funeral Support — each a score-delta on a Poor→Superior % gap scale.
- "Additional items covered" per insurer, a "same/similar" list, and an **Exclusions** list.
- A 1-month validity window and a full page of **Replacement Business Disclosure** + disclaimers.

### Where PolicyIQ already wins

| Dimension | Quote Monster | PolicyIQ |
|---|---|---|
| Evidence | Opaque scores, no proof | Extracted facts with **page-level citations**, confidence, plain-English rationale |
| Breadth | Strictly 2 products | **Many insurers** compared at once (8 life insurers today) |
| Criteria | Flexibility features | Substantive: TPD definition, trauma conditions, occupation restrictions |
| Personal data | Stores client name + demographics | **Stores nothing personal** (see §3) |

## 3. Core principles

1. **No personal information (PI), ever.** Comparisons are computed on-demand from extracted
   facts. Life inputs (age, smoker status, occupation) and any future pricing inputs (sum
   insured, etc.) are **ephemeral in-memory filters** — never written to the database, never
   tied to a person, no names or contact details collected. This is a deliberate security and
   privacy differentiator versus Quote Monster, which embeds and stores client PI in reports.
2. **Evidence-based, not score-based.** Every comparison point traces to a document page
   (`SourceRef`: insurer, document, page, paragraph, confidence). "Why this score?" is always
   answerable from weights + facts.
3. **Deterministic grading.** Turning an extracted, citation-verified fact into a comparable
   score is a plain function of that fact — no second LLM call, no extra hallucination surface
   (carried over from `09-LIFE-INSURANCE-SLICE.md`).

## 4. Compliance note (read before the pricing workstream)

The original scope (`09-LIFE-INSURANCE-SLICE.md`, `00-CHALLENGE.md` #1, `01-ARCHITECTURE.md`)
deliberately kept PolicyIQ **document-derived and informational, with no $ premium**, to stay
out of "quote-comparison-site" territory and the harder **FMA/FAP financial-advice risk**.

Adding **pricing** and a **paid head-to-head recommendation-style report** moves PolicyIQ
toward that territory. Before shipping Workstream C (pricing) or marketing the $49 report as
advice, decide the compliance posture:

- Operate as an **informational comparison** with prominent "not financial advice / seek a
  registered financial adviser" disclaimers (the approach Quote Monster uses), **or**
- Bring the product under appropriate **FMA/FAP** coverage.

This is a product-owner decision; engineering should not silently drop the no-premium guardrail.
The head-to-head *feature* comparison (Workstream D) stays comfortably informational; it is
*pricing* that triggers the advice-risk question.

## 5. Monetization & access model

Two tracks, both gated by **named-user accounts with API tokens** (auth per
`10-AUTH-AND-ACCOUNTS.md` — already designed, not yet built):

| Track | Price | Model | Who it's for |
|---|---|---|---|
| **Subscription** | **$49 / month** | Flat-rate named-user access to the UI + head-to-head reports, with a personal API token | Individual advisers and small practices — directly undercuts Research Monster's >$99 |
| **Company API** | **$20 / credit**, minimum **10 credits / month** ($200/mo floor) | **1 credit = 1 comparison** generated via the API; credits pooled across the company's named users | Companies embedding PolicyIQ comparisons into their own systems |

- **Credit rule:** the API consumes **1 credit per comparison generated**. Company access is
  metered against a credit ledger with a 10-credit monthly minimum; subscription access is
  flat-rate (not metered). Confirmed metering unit: *1 credit = 1 API call = 1 comparison*.
- **Named users + tokens:** every user has an account and a long-lived API key (the "API Keys"
  card in `10-AUTH-AND-ACCOUNTS.md`); paying for the UI also grants API access.
- **No PI stored** regardless of track (see §3) — credits meter *comparisons*, never people.
- The **credit ledger / subscription billing is net-new** (not yet designed); the subscription
  flag and credit balance hang off the existing `USER` / account model from `10-AUTH-AND-ACCOUNTS.md`.

## 6. Workstreams

### A. Taxonomy alignment (to the AdviceLink 3-level model + client types)

Target model from the AdviceLink product catalogue: **Level 1 Risk Area → Level 2 Risk Event
→ Level 3 Product**, plus a **client-type** axis (Retail/Business, Commercial, Group).

- Add a `client_type` dimension: `retail | business | commercial | group` on the product /
  policy-version. Highest-leverage change — unlocks Business/Commercial/Group without
  duplicating the risk-event taxonomy.
- Add a **Level-3 named-product layer** under `insurer × product_type × client_type`
  (e.g. Southern Cross → health → retail → UltraCare).
- Split the single `life_cover` product into per-event comparable lines:
  `life / trauma / tpd / income_protection / mortgage_protection`.
- Add missing risk events: `mortgage_protection`; a `business_disability` area (key person,
  business expenses, rural continuity, debt protection, shareholder protection).

Coverage today: PolicyIQ `personal_risk` children already ~80% match AdviceLink Level-2
(death, tpd, trauma, income_protection present; mortgage_protection missing). PolicyIQ
`medical` children (surgical, cancer_treatment, dental, optical…) map to AdviceLink **benefit
attributes**, not products — useful, but the product shells that group them are absent.
Business/Commercial/Group categories are absent.

### B. Competitive parity features

- **Heatmap-style per-criterion winner highlighting** in the life view — make "who wins this
  row" instant (colour/badge on the best insurer per criterion).
- **Add QM-style flexibility criteria** to life grading: cover conversion, special events
  increase, inflation adjustment, grief & funeral support. (Life grading currently has six
  criteria in `backend/app/services/grading.py`: `tpd_definition`, `trauma_conditions`,
  `occupation_restrictions`, `premium_structure`, `waiver_of_premium`, `automatic_benefits`.)
- **Insurer financial-strength ratings** (Fitch / AM Best) as a trust signal.
- **Freshness / "as-of" dating** — surface "extracted from [document] on [date]" per comparison
  (parallels QM's validity window).

### C. Pricing comparison (phase 2, separate pipeline)

Pricing is **not** produced by the document-extraction pipeline — policy PDFs describe cover,
not premiums. QM gets pricing from insurer rate feeds / adviser quoting integrations. A pricing
feature needs its own data source, and feasibility is uneven:

| Product line | Feasibility | Why |
|---|---|---|
| Health | ✅ Most feasible | Southern Cross / nib / UniMed publish public-ish price guides |
| Life | ⚠️ Hardest | AIA / Fidelity / Partners rates are adviser-channel, no public API → needs partnerships or rate tables |
| General (car/home) | ⚠️ Messy | Public quote flows exist but are JS-heavy and highly personalised |

No-PI compatible (inputs stay ephemeral). **Subject to the §4 compliance decision.** Build
after the head-to-head; start health-first.

### D. $49 head-to-head report (the paid differentiator)

A polished, shareable head-to-head comparison report built from the existing extraction
pipeline: multi-insurer (not just 2-way), cited to document pages, with winner highlighting
(Workstream B) and the AdviceLink-aligned taxonomy (Workstream A). No PI required. This is
fully feasible now and is the commercial centrepiece.

## 7. Sequencing

1. **Phase 1 — head-to-head that beats QM (no pricing needed):** Workstream A (taxonomy) +
   Workstream B (competitive features) + Workstream D (the $49 report). Ships the differentiator.
2. **Phase 2 — pricing as table-stakes:** Workstream C, health-first, after the §4 compliance
   decision and once insurer rate access is confirmed.

## 8. Current state & pending

- **Health ingestion running:** Southern Cross (UltraCare), nib (Premium Hospital), UniMed
  (Hospital Select) via `.github/workflows/ingest.yml` — populates the Health split.
- **Pending UI tasks:** terminology pass (use "extracted"/"facts", remove scraping/crawler/
  pipeline language); document title-casing (`_title_from_storage_key` in
  `backend/app/api/v1/documents.py`); Risk Explorer rebuild as a top-down mindmap ending at
  insurers; admin-only document download lock.
- **Deployed:** backend auto-deploys to VPS (`api.policyiq.nz`); frontend deploys to GitHub
  Pages (`policyiq.nz`) via `.github/workflows/deploy-frontend.yml`.

## 9. Technical anchors

| Path | What |
|---|---|
| `backend/app/services/grading.py` | Life grading engine (6 weighted, sourced criteria) |
| `backend/app/domain/risk_area_taxonomy.py` | Risk-area taxonomy (nested tree, `/risk-areas`) |
| `backend/app/api/v1/compare.py` | `/compare/life` (graded), `/compare/general` (fact-diff) |
| `backend/app/api/v1/documents.py` | Document listing + `_title_from_storage_key` |
| `workers/crawler/policyiq_crawler/registry.py` | Insurer seeds (incl. `HEALTH_INSURER_SEED`) |
| `frontend/src/views/CompareView.vue` | 9 flat insurance splits (general fact-diff / life graded) |
| `frontend/src/views/RiskExplorerView.vue` | Risk Explorer (to be rebuilt as mindmap) |
| `.github/workflows/ingest.yml` | Crawl + ingest workflow (VPS, LLM extraction) |
