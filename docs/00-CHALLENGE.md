# Challenging the Brief

The original brief (preserved in full at the bottom of this repo's PR description) asks for
"New Zealand's leading insurance intelligence platform," built like the founder intends to sell
for £100M, with a 12-week roadmap covering crawling, OCR, multi-provider AI extraction,
vector search, a comparison engine, a full SaaS frontend, admin tooling, auth, and a
7-vertical future roadmap (mortgages, KiwiSaver, credit cards, utilities, broadband,
investments).

That brief is directionally right about the opportunity and wrong about several load-bearing
details. Below is the pushback, in order of how much it should change the plan.

## 1. The single biggest gap: this may be regulated financial advice

Nothing in the brief mentions the Financial Markets Conduct Act 2013 or the FMA's Financial
Advice Provider (FAP) licensing regime. That's not a footnote — it determines which features
you can ship at all.

- **Retrieval + citation of public policy documents** ("here's what AMI's PDS says on page 12
  about retaining walls") is almost certainly fine. You're indexing public documents, not
  advising.
- **"Which insurer covers X" answered against a specific user's stated situation**, and
  especially the roadmap items **recommendation engine**, **claim probability estimator**, and
  **policy gap analysis**, start to look like regulated financial advice under NZ law the moment
  the system implies "you should pick this policy." Giving that kind of advice without being a
  licensed FAP (or acting under one) is a genuine legal exposure, not a hypothetical.

**Recommendation:** get this in front of counsel before Phase 1 ships publicly, and treat FAP
licensing as a gate on specific features, not the whole product. Concretely:
- Phase 1 ships as a **document search and comparison tool** with an explicit "this is
  information, not financial advice" posture baked into the UI (not just a footer disclaimer —
  answer framing itself: "Policy X's wording states..." not "You should choose X").
- Recommendation engine, gap analysis, and claim probability estimator move to a gated future
  phase behind either a FAP license or a partnership with a licensed adviser who reviews/signs
  off on that logic.
- Health and life insurance (Southern Cross, nib, AIA, Partners Life, Fidelity Life, Accuro,
  UniMed) carry the highest advice-adjacent risk (e.g. "which policies cover ADHD" is close to
  personal underwriting advice) — sequence these *after* the compliance posture is settled, not
  in the initial insurer set.

## 2. "Never hallucinate" and "always cite sources" are marketing lines, not engineering specs

You cannot guarantee an LLM never hallucinates. What you *can* engineer is a system that fails
closed: every claim is grounded in retrieved chunks, every citation is mechanically verified
against the source text before being shown, and the system answers "not found in indexed
documents" rather than guessing when retrieval confidence is low. That's a testable, gradeable
property — "never hallucinate" isn't. Section 5 (AI extraction strategy) and the query engine
design specify this as **mandatory citation verification + confidence-gated abstention**, with a
labeled eval set to measure precision/recall over time. Ship the honest version of the promise.

## 3. The stack has three-way redundancy that will slow you down, not speed you up

The brief lists Docling, MinerU, *and* PyMuPDF for extraction/OCR, and OpenAI, Gemini, *and*
Anthropic for extraction/generation, all in initial scope. Running three OCR pipelines and three
LLM providers against every document from day one triples your integration surface, triples
your eval burden, and triples your bill — for a benefit (redundancy) you don't need until you've
proven you need it.

**Recommendation:**
- **PyMuPDF** as the fast path for native-text PDFs (majority case).
- **Docling** for structure-aware parsing of complex/scanned documents (tables, multi-column
  PDS layouts). Hold MinerU in reserve — add it only if a concrete class of documents fails on
  Docling in the eval set.
- **One primary LLM for extraction and query answering**, with a second provider wired in as an
  automatic failover (not a parallel three-way call). Given the "cite exact page/paragraph,
  never answer without evidence" requirement, a model with strong long-context grounding and
  instruction-following on citation format is the right primary; keep the integration provider-
  agnostic so swapping is a config change, not a rewrite.

This halves build time without reducing quality, and leaves the redundancy story available for
Phase 2 once you know which documents actually need it.

## 4. The 12-week roadmap is realistic for a Phase 1 slice, not for the brief as written

As written, "12 weeks" is asked to cover: crawler, version detection, OCR, AI extraction,
14-table relational schema, vector search, comparison engine with 3 export formats, change
detection, a 7-page Vue SaaS frontend with dark mode, an admin console, JWT + RBAC, audit
logging, Docker + CI/CD, and a full test suite — for an unbounded set of insurers and products.
That's a multi-quarter build for a team, not a 12-week solo sprint, and treating it as 12 weeks
invites exactly the "MVP with shortcuts" the brief says to avoid.

**Recommendation:** keep 12 weeks, shrink the surface, not the quality:
- **5–6 insurers to start** (house/contents and travel only — see #1 on why health/life waits),
  not all 18+.
- **No billing, no multi-tenant SaaS commerce layer in Phase 1.** Ship as an internal/beta tool
  with real auth and RBAC (consumer/broker/admin roles), add Stripe and self-serve signup once
  the extraction pipeline's accuracy is proven. Bolting on billing before the core data quality
  is trustworthy is optimizing the wrong risk.
- Every other vertical (mortgages, KiwiSaver, credit cards, utilities, broadband, investment
  products) stays in the architecture as a first-class extension point (schema and pipeline are
  product-type-agnostic — see `02-DATABASE-ERD.md`), but isn't built until Phase 1 insurance
  is live and its extraction accuracy is measured, not assumed.

See `07-ROADMAP.md` for the resequenced 12 weeks.

## 5. Scraping insurer PDFs is a legal and relationship question, not just a technical one

Crawling and permanently archiving copyrighted PDS/wording documents from 18+ insurers'
websites needs a ToS/robots.txt check per insurer, a rate-limiting posture that doesn't look
like an attack, and a policy on what you republish (excerpts with citation, not full documents,
mirroring fair-dealing norms) vs. what you only index internally. Longer term, the strongest
version of this business goes and gets data-share agreements with insurers directly — being
adversarial with the data source you depend on is a fragile foundation for something you intend
to sell. `04-CRAWLER-STRATEGY.md` builds this in as a first-class constraint (per-insurer
crawl policy config, robots.txt compliance, a takedown process), not an afterthought.

## 6. Missing entirely from the brief

- **Who's the customer?** The brief mixes consumer-facing ("compare AMI vs Tower"),
  broker-facing (broker portal), and platform/API (affiliate tracking, quote automation)
  personas without picking a primary one. Phase 1 should pick one ICP — recommend **consumers
  and brokers researching coverage**, with a licensed-B2B-API product as the Phase 2 monetization
  path once the corpus and accuracy are proven. This is a product decision worth you weighing in
  on; the roadmap defaults to it but it's easy to redirect.
- **Cost control.** Re-extracting and re-embedding every document on every detected change,
  across hundreds of PDFs, is an ongoing LLM spend line, not a one-time cost. Needs a budget and
  a "only re-run extraction on the diff'd section, not the whole document" strategy from day one.
- **Evaluation methodology.** "Confidence scoring" isn't the same as knowing your extraction is
  correct. You need a hand-labeled gold set (even 50-100 claims per insurer) to measure
  precision/recall and catch regressions before they reach users.
- **Observability.** The admin page in the brief shows crawler/extraction status, but there's no
  mention of structured logging, tracing, or alerting for the actual failure modes (crawl breaks
  when an insurer redesigns their site, extraction confidence drops after a model swap, etc.).

None of this changes the ambition of the brief — it changes the sequencing and puts a legal
gate in front of the highest-risk features. The rest of `docs/` reflects the revised plan.
