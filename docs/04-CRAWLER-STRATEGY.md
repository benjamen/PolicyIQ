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

## Discovery pipeline

```
Seed insurer website_root
  → Sitemap.xml check (fast path, most sites have one)
  → Playwright crawl of allowed paths (fallback for JS-rendered nav/product pages)
  → PDF link extraction (href ending .pdf, and "Download PDS"/"Policy Wording" link text
    heuristics — insurer sites are inconsistent, so this stays a maintained per-insurer rule
    set, not a single generic regex)
  → Candidate documents queued to Downloader
```

Playwright is used deliberately, not by default: static `requests`/sitemap fetch is tried first
per URL, and Playwright (headless Chromium) only engages when a page requires JS rendering to
expose links. This keeps crawl cost and detection risk down.

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
