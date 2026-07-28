# API Specification (summary)

FastAPI serves the canonical OpenAPI schema at `/openapi.json` (auto-generated from route
models — this doc is the human-readable index, not a source of truth to keep in sync by hand).

Base path: `/api/v1`. All responses are JSON. Every response that includes an AI-generated claim
includes a `citations[]` array — this is a response-shape invariant, not optional per-endpoint
behavior.

## Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (consumer/broker; admin created via seed/admin-only) |
| POST | `/auth/login` | Returns access + refresh JWT |
| POST | `/auth/refresh` | Rotate access token |
| POST | `/auth/logout` | Revoke refresh token |

Rate limits (Redis token bucket, per-user + per-IP fallback for anonymous):
- `search`/`compare` (LLM-backed): 30 req/min authenticated, 5 req/min anonymous.
- Everything else: 120 req/min.
- `429` responses include `Retry-After`.

## Search (query engine)
| Method | Path | Description |
|---|---|---|
| POST | `/search` | `{query, filters?}` → retrieval + LLM answer + `citations[]`. `filters` optional (insurer, product_type, date_range) |
| GET | `/search/history` | Caller's past questions/answers |

Response shape:
```json
{
  "answer": "AMI's House policy (v3, effective 2025-11-01) covers retaining wall damage up to $20,000 under Section 4.2...",
  "confidence": 0.87,
  "response_mode": "informational",
  "citations": [
    {"insurer": "AMI", "document": "House Policy Wording v3", "page": 12, "paragraph": "4.2", "excerpt": "...", "verified": true}
  ],
  "insufficient_evidence": false
}
```
When retrieval or citation-verification fails the confidence bar, `insufficient_evidence: true`
and `answer` is a fixed "not found in indexed documents" message — never a best-effort guess.

## Compare
| Method | Path | Description |
|---|---|---|
| POST | `/compare` | `{policy_version_ids[]}` → structured side-by-side diff (benefits/limits/exclusions/waiting periods) |
| GET | `/compare/{id}/export?format=pdf\|xlsx\|md` | Export a saved comparison |

## Policy / Product / Insurer
| Method | Path | Description |
|---|---|---|
| GET | `/insurers` / `/insurers/{id}` | Insurer registry + their products |
| GET | `/products` / `/products/{id}` | Products, filterable by `vertical`, `product_type` |
| GET | `/policies/{id}` | Policy detail incl. current + historical `PolicyVersion`s |
| GET | `/policies/{id}/versions/{version_id}` | Full extracted structure for one version |

## Documents
| Method | Path | Description |
|---|---|---|
| GET | `/documents/{id}` | Metadata + presigned R2 URL |
| GET | `/documents/{id}/sections` | Extracted sections for the document explorer view |

## Changes
| Method | Path | Description |
|---|---|---|
| GET | `/changes?since=&insurer=&product_type=` | Change feed (backs "Recent Changes" page) |
| GET | `/changes/{id}` | Single change event with before/after diff |

## Admin (role: admin only)
| Method | Path | Description |
|---|---|---|
| GET | `/admin/crawler/status` | Per-insurer last-crawl time, success/failure |
| GET | `/admin/extraction/queue` | Queued/failed extraction jobs |
| GET | `/admin/extraction/confidence` | Low-confidence extraction report (drives review queue) |
| GET | `/admin/embeddings/status` | Coverage: documents without embeddings |
| GET | `/admin/search-logs` | Query log incl. `insufficient_evidence` rate — the single most
important product-quality metric, tracked from day one |
| POST | `/admin/documents/{id}/reprocess` | Force re-run extraction on one document |

## Auth model on responses
- `consumer`/`broker`: full read access to search/compare/policy/insurer/document/changes.
- `admin`: adds `/admin/*`.
- No endpoint returns `response_mode: "advisory"` in Phase 1 — the field exists in the schema
  (forward-compatible) but the query engine never sets it while the feature flag is off (see
  `01-ARCHITECTURE.md` compliance boundary).

## Versioning & docs
`/api/v1` prefix now; breaking changes get `/api/v2` rather than in-place breaking changes.
OpenAPI spec is generated, linted in CI, and published as part of the docs site — brokers/B2B
consumers (Phase 2) get a real contract, not a wiki page that drifts.
