# Database ERD

Relational core in PostgreSQL; embeddings live in the same database via `pgvector` (one store,
one backup story, one transaction boundary between a fact and its embedding — avoids the
drift you get from a separate vector DB).

Schema is **vertical-agnostic by design** (see `01-ARCHITECTURE.md`): `Product.vertical` and
`Product.product_type` are the only fields that vary by product line; every other table is
shared by insurance, mortgages, KiwiSaver, etc. when those phases start.

```mermaid
erDiagram
    INSURER ||--o{ PRODUCT : offers
    PRODUCT ||--o{ POLICY : "has instances of"
    POLICY ||--o{ POLICY_VERSION : "versioned as"
    POLICY_VERSION ||--o{ DOCUMENT : "sourced from"
    POLICY_VERSION ||--o{ SECTION : contains
    SECTION ||--o{ BENEFIT : contains
    SECTION ||--o{ LIMIT : contains
    SECTION ||--o{ EXCLUSION : contains
    SECTION ||--o{ DEFINITION : contains
    SECTION ||--o{ WAITING_PERIOD : contains
    SECTION ||--o{ OPTIONAL_BENEFIT : contains
    DOCUMENT ||--o{ EMBEDDING : "chunked into"
    SECTION ||--o{ EMBEDDING : "backs"
    DOCUMENT ||--o{ CHANGE_EVENT : "diffed into"
    QUESTION ||--o{ ANSWER : produces
    ANSWER ||--o{ ANSWER_CITATION : cites
    ANSWER_CITATION }o--|| EMBEDDING : references
    USER ||--o{ QUESTION : asks
    USER ||--o{ AUDIT_LOG : generates
    USER ||--o{ API_KEY : issues

    INSURER {
        uuid id PK
        text name
        text website_root
        text crawl_policy_json
        timestamptz created_at
    }
    PRODUCT {
        uuid id PK
        uuid insurer_id FK
        text vertical "insurance | mortgage | kiwisaver | ..."
        text product_type "contents | travel | health | home_loan | ..."
        text name
        timestamptz created_at
    }
    POLICY {
        uuid id PK
        uuid product_id FK
        text name
        timestamptz created_at
    }
    POLICY_VERSION {
        uuid id PK
        uuid policy_id FK
        int version_number
        date effective_date
        text status "current | superseded"
        timestamptz created_at
    }
    DOCUMENT {
        uuid id PK
        uuid policy_version_id FK
        text doc_type "pds | wording | brochure | claims_guide | form"
        text storage_key "R2 object key"
        text sha256_hash
        text etag
        text last_modified
        int page_count
        text source_url
        timestamptz downloaded_at
    }
    SECTION {
        uuid id PK
        uuid policy_version_id FK
        uuid document_id FK
        text heading
        int page_start
        int page_end
        text paragraph_ref
    }
    BENEFIT {
        uuid id PK
        uuid section_id FK
        text name
        text description
        numeric monetary_limit
        numeric percentage_limit
        boolean is_automatic
        int page
        text paragraph_ref
        numeric confidence
    }
    LIMIT {
        uuid id PK
        uuid section_id FK
        text limit_type
        numeric amount
        text currency
        int page
        text paragraph_ref
        numeric confidence
    }
    EXCLUSION {
        uuid id PK
        uuid section_id FK
        text description
        int page
        text paragraph_ref
        numeric confidence
    }
    DEFINITION {
        uuid id PK
        uuid section_id FK
        text term
        text definition_text
        int page
        text paragraph_ref
    }
    WAITING_PERIOD {
        uuid id PK
        uuid section_id FK
        text applies_to
        int days
        int page
        text paragraph_ref
        numeric confidence
    }
    OPTIONAL_BENEFIT {
        uuid id PK
        uuid section_id FK
        text name
        text description
        numeric additional_premium
        int page
        text paragraph_ref
    }
    EMBEDDING {
        uuid id PK
        uuid document_id FK
        uuid section_id FK
        vector embedding "pgvector, dim per model"
        text chunk_text
        int page
        text paragraph_ref
        text embedding_model
    }
    CHANGE_EVENT {
        uuid id PK
        uuid document_id FK
        uuid previous_document_id FK
        text change_type "added | removed | benefit_increase | benefit_decrease | exclusion_change"
        text summary
        text diff_ref
        timestamptz detected_at
    }
    USER {
        uuid id PK
        text email
        text role "consumer | broker | admin"
        text password_hash "nullable - SSO-only users have none"
        text sso_provider "nullable - e.g. entra"
        text sso_subject "nullable, unique when set - IdP subject/oid claim"
        timestamptz created_at
    }
    API_KEY {
        uuid id PK
        uuid user_id FK
        text key_hash "raw key never stored"
        text label
        timestamptz created_at
        timestamptz last_used_at
        timestamptz revoked_at "nullable"
    }
    QUESTION {
        uuid id PK
        uuid user_id FK
        text query_text
        timestamptz created_at
    }
    ANSWER {
        uuid id PK
        uuid question_id FK
        text answer_text
        numeric confidence
        text response_mode "informational | advisory"
        timestamptz created_at
    }
    ANSWER_CITATION {
        uuid id PK
        uuid answer_id FK
        uuid embedding_id FK
        boolean verified "text-match check passed"
    }
    AUDIT_LOG {
        uuid id PK
        uuid user_id FK
        text action
        jsonb payload
        timestamptz created_at
    }
```

## Notes

- **`Section` is the join point** between structure (page/paragraph location) and every
  extracted-fact table — this is what lets the comparison engine say "AMI's retaining-wall
  clause is in Section 4.2, page 12" rather than just "somewhere in this PDF."
- **`ANSWER_CITATION.verified`** is written by the citation-verification step in the query
  engine (see `05-AI-EXTRACTION-STRATEGY.md`): a boolean the API refuses to omit. An answer
  with zero verified citations is not returned to the user — it's logged and surfaced in
  admin as a retrieval gap instead.
- **`confidence`** exists on every extracted-fact table, not just as a global answer score —
  this is what lets the admin console show "which specific benefit-extractions are low
  confidence" (per the brief's admin requirement) rather than only document-level confidence.
- No per-tenant partitioning in Phase 1 (single shared corpus). If B2B API licensing becomes a
  real product (see challenge doc #6), tenant scoping is added at the `USER`/`API_KEY` layer, not
  by duplicating the document corpus.
- **`USER.password_hash` is nullable** — password auth and Microsoft Entra SSO are both valid
  ways to authenticate (see `10-AUTH-AND-ACCOUNTS.md`); an SSO-only user has `sso_provider`/
  `sso_subject` set and no password. `role` stays PolicyIQ-owned regardless of login method — no
  external identity provider's group/role claims are trusted for RBAC.
- **`API_KEY`** is separate from browser sessions: long-lived, `key_hash`-verified (never the raw
  key), no refresh/rotation flow. This is the mechanism for the B2B/broker "API option" product
  surface referenced above, and for scripts/integrations that can't do an interactive login
  redirect.
