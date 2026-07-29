# Crawler Strategy

## Legal posture (first-class constraint, not an afterthought)

Before any insurer is added to the registry:
1. Fetch and respect `robots.txt`. If it disallows the paths we need, that insurer needs a
   direct data-share conversation before automated crawling, not a workaround.
2. Rate-limit per-insurer (default: 1 request per 2 seconds, configurable per insurer,
   randomized jitter) — the goal is to look like a considerate visitor, not to evade detection.
   Identify with a real, descriptive User-Agent and a contact URL, so an insurer that notices
   the traffic can reach us instead of just blocking us.
3. Store a `crawl_policy_json` per insurer (`INSURER.crawl_policy_json` in the ERD) recording:
   allowed paths, rate limit, contact status, and a `blocked` flag an admin can set instantly if
   an insurer asks us to stop.
4. Public excerpts (citations shown to users) are short, attributed quotations, not full
   document republication. Full documents are stored for internal indexing/retrieval only.
5. A visible takedown/contact process (`legal@` or equivalent) for insurers who want to opt out
   or dispute an excerpt.

This is what makes the crawler sustainable rather than a legal liability that surfaces the day
this platform is worth acquiring.

## Insurer registry

`Insurer` rows are seeded manually for the initial set (see `07-ROADMAP.md` for which insurers
launch first), then the registry supports adding insurers dynamically. Each insurer config
specifies: `website_root`, allowed crawl paths/patterns, and doc-type heuristics (URL patterns
or page structures that typically hold PDS/wording/brochures).

## No government registry for policy wordings (researched 2026-07-30)

Before building any document-hub discovery logic, checked whether NZ has a KiwiSaver-style
central government register for insurance policy wordings that would make per-insurer crawling
unnecessary. It doesn't, for this product category:

- KiwiSaver and other managed investment products/securities must file on the Companies Office
  **Disclose Register** under the Financial Markets Conduct Act 2013. Confirmed directly against
  the register's own stated scope ("debt and equity securities, derivatives and managed
  investment products, and managed investment schemes") — insurance isn't mentioned. Traditional
  life/trauma/TPD/income-protection insurance is an insurance *contract*, not a "financial
  product" in the FMC Act's sense, so it's simply out of scope for that register.
- What does regulate NZ life insurers — RBNZ's Register of Licensed Insurers (licensing/solvency
  status only), the Financial Service Providers Register (registration only), FMA's Conduct of
  Financial Institutions regime (a public *fair-conduct-programme summary*, not policy wordings),
  and the incoming Contracts of Insurance Act 2024 (plain-language + disclosure *duties between
  insurer and policyholder*, in force by Nov 2027) — none of it mandates publishing wordings
  centrally, or even publicly.
- Industry submissions on that same law reform explicitly flagged that some insurers have no
  publicly available policy wording at all ("only through application") — matching what this
  crawler found firsthand: Partners Life's and Asteron Life's product pages each link only to a
  marketing brochure + claim form, never a full wording.
- Comparison/aggregator sites (LifeDirect, Compare.org.nz, MoneyHub, etc. — already excluded from
  the registry, see `registry.py`) aren't a shortcut either: checked LifeDirect directly, and its
  `/compare/*` pages are a client-side quote-rating tool requiring a filled-in form, not a
  document listing. Even if they were, citing a rival's summarized output instead of the
  insurer's own primary-source text would undermine this project's citation-verification design.

Conclusion: each insurer's own site is genuinely the only source. There's no registry to
cross-reference for documents (only for which entities are licensed insurers at all, which
`discover_insurers()`'s still-pending RBNZ cross-reference TODO is about) — so the crawler has to
go looking for each insurer's own documents hub directly, per below.

## Discovery pipeline

```
Seed insurer website_root
  → Also seed known documents-hub path patterns directly (registry.py's
    DEFAULT_DOCUMENT_HUB_PATHS - /policy-wording, /important-information, /useful-documents,
    etc.) - a homepage-rooted crawl alone can miss a real hub page that isn't linked prominently
    from anywhere reachable within DEPTH_LIMIT (confirmed: Asteron Life's /important-information
    is real, live content that a pure link-following crawl didn't reach)
  → Sitemap.xml check (fast path, most sites have one)
  → Playwright rendering, per URL (fallback for JS-rendered nav/product pages)
  → PDF link extraction (href ending .pdf, and "Download PDS"/"Policy Wording" link text
    heuristics — insurer sites are inconsistent, so this stays a maintained per-insurer rule
    set, not a single generic regex)
  → Candidate documents queued to Downloader
```

Playwright is used deliberately, not by default: static fetch is tried first per URL, and
Playwright (headless Chromium, honestly identified with the same User-Agent as every other
request - no stealth/fingerprint-hiding) only engages when a page requires JS rendering to
expose links. This keeps crawl cost down and isn't meant to defeat a site's deliberate
anti-automation controls (a different, out-of-scope problem - see `policy_document_spider.py`).

## Document classification

Each discovered PDF is classified by URL/link-text pattern + a lightweight first-page text
check into: `pds`, `wording`, `brochure`, `claims_guide`, `underwriting_guide`, `form`,
`renewal_doc`, `faq`. Classification confidence below threshold routes to an admin review queue
rather than guessing silently — visible in `/admin/extraction/queue`.

## Download & version detection

For every candidate document:
1. HEAD request first — compare `ETag` and `Last-Modified` against the current `Document` row
   for that URL. Unchanged → skip, no download.
2. If changed (or first-seen), download, compute `sha256`. If the hash matches an existing
   `Document` for a *different* URL (insurer moved/renamed a file), link it as the same document
   rather than creating a duplicate — this is the "document similarity" dedup the brief calls
   for, implemented as hash-first, falling back to a text-similarity check (cosine over a cheap
   embedding of the first page) only when the hash differs but content may not have.
3. New/changed documents get a new `Document` row + upload to R2 (`storage_key` scheme:
   `{insurer}/{product_type}/{doc_type}/{sha256[:12]}-{filename}`), and increment
   `PolicyVersion.version_number`. **Never overwrite** — this is enforced by storage_key being
   content-addressed, not just a policy statement.
4. Triggers the extraction pipeline for new/changed documents only.

## Scheduling

Celery beat, daily crawl per insurer by default, staggered across the day (not all 18 insurers
at midnight) to keep load predictable and polite. High-change insurers can be scheduled more
frequently once we have data on how often they actually update documents — no reason to hit a
site daily if it updates quarterly.

## Failure handling

Every crawl run logs to `/admin/crawler/status`: last success, last failure + reason (site
redesign broke selectors, robots.txt changed, timeout, 403). Three consecutive failures on an
insurer auto-disables that insurer's schedule and raises an admin alert rather than retrying
indefinitely against a site that may have blocked us.
