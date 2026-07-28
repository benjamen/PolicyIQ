# AI Extraction & Query Strategy

## OCR routing (tightened from the original three-library proposal — see challenge doc #3)

```
Document in
  → PyMuPDF text-layer check: does the PDF have a usable native text layer covering
    ≥95% of pages with real (non-garbled) text?
      YES → PyMuPDF fast path (text + layout blocks + page/paragraph coordinates)
      NO  → Docling (structure-aware parsing: tables kept intact, multi-column PDS layouts
            handled, scanned-page OCR)
  → Output: page-anchored text blocks with bounding boxes, feeding both Section creation
    and chunking for embeddings.
```

MinerU is not in the initial pipeline. If the eval set (below) shows a class of documents
(e.g. a specific insurer's scanned legacy wording) where Docling's output quality is
measurably worse, MinerU gets evaluated as an addition for that class — not integrated
speculatively.

## Extraction (structured JSON, validated, retried)

Per `Section`, the primary LLM is prompted to extract the categories from the brief (benefits,
limits, exclusions, waiting periods, eligibility, optional/automatic covers, claims process,
cancellation, premium discounts, special conditions, all monetary/percentage figures) as
**structured output validated against a Pydantic schema**. On schema-validation failure: retry
up to 2x with the validation error fed back to the model; persistent failure routes the
section to the admin review queue rather than silently dropping data.

Every extracted fact carries:
- `page`, `paragraph_ref` — taken from the OCR/parse stage's coordinates, not re-inferred by
  the LLM (the LLM is not a trustworthy source of "what page was this on"; the parser is).
- `confidence` — model-reported confidence, calibrated against the eval set below (a model
  that says "0.9" needs to actually be right ~90% of the time for that number to mean anything;
  this is checked, not assumed).

## Citation verification (the mechanism behind "never hallucinate")

Before any answer or extracted fact is persisted/returned:
1. Take the claimed `document_id` + `page` + `paragraph_ref`.
2. Fetch the actual source text at that location from the parsed document.
3. Run a text-entailment/overlap check: does the source text actually support the claim
   (substring/fuzzy match for direct quotes; a lightweight entailment check for paraphrased
   claims)?
4. Set `ANSWER_CITATION.verified` accordingly. Answers with zero verified citations are not
   shown — they log to `insufficient_evidence` instead (see API spec).

This turns "never hallucinate" from a prompt instruction (which doesn't reliably work) into a
mechanical gate the system enforces regardless of what the model outputs.

## Query engine (retrieval → answer)

```
User question
  → Embed query (same model as corpus embeddings)
  → pgvector similarity search, filtered by any explicit filters (insurer/product_type/date)
  → Re-rank top-k by a cheap cross-encoder or the LLM itself scoring relevance
  → LLM answers ONLY from retrieved chunks, required to cite chunk IDs inline
  → Citation verification (above) on every cited chunk
  → If verified citations < 1 or confidence < threshold → insufficient_evidence response
  → Else → answer + citations[] returned
```

## Chunking

Chunk boundaries follow `Section` boundaries, not fixed token windows — a benefit table or a
clause never gets split mid-table (per the brief's "do not split tables" requirement). Tables
detected by Docling are kept as a single chunk with a serialized-table representation
(markdown table in the chunk text) so the LLM can reason over the whole table at once.

## Change-triggered re-extraction (cost control — addresses challenge doc #6)

On a detected document change, extraction runs a section-level diff against the previous
version first (text diff, not LLM). Only sections with material text changes are re-extracted;
unchanged sections carry forward their existing extracted facts and embeddings. This is what
keeps ongoing LLM spend proportional to actual document churn instead of re-processing entire
documents on every crawl.

## Evaluation (new — not in the original brief)

A hand-labeled gold set (target: 50-100 claims per insurer across benefits/limits/exclusions,
built during Phase 1 as documents are onboarded) is used to compute precision/recall of
extraction and of citation verification. This eval runs in CI against any change to extraction
prompts or provider/model swaps — a prompt or model change that regresses accuracy is caught
before it reaches production, not discovered by a user getting a wrong answer. `insufficient_
evidence` rate and citation-verification pass rate are tracked as first-class product metrics
in `/admin/search-logs`, not just uptime/latency.

## Provider adapters

Primary LLM handles both extraction and query answering through the `shared/providers/llm.py`
interface (see `01-ARCHITECTURE.md`). Failover provider is wired but only invoked on primary
error/timeout, logged distinctly so we can see how often failover actually triggers — that data
is what justifies (or doesn't) building out true multi-provider parallel extraction later.
