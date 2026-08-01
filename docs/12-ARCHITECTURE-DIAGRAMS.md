# Architecture Diagrams — PolicyIQ Scraping System

## 1. End-to-End Pipeline Flow

```mermaid
flowchart TB
    subgraph Scheduler["⏰ Scheduler"]
        WEEKLY["Weekly Crawl<br/>Mon 02:00 NZST"]
        DAILY["Daily HEAD Check<br/>06:00 NZST"]
        MANUAL["Admin Trigger<br/>Ad-hoc"]
    end

    subgraph Discovery["🔍 Stage 1: Discovery"]
        ROBOTS["robots.txt<br/>Validation"]
        SITEMAP["Sitemap.xml<br/>Fetch"]
        CRAWL["Link-Following<br/>Crawl"]
        PLAYWRIGHT["Playwright<br/>Fallback"]
        CLASSIFY["Document<br/>Classification"]
        BROCHURE_DISC["Brochure/Asset<br/>Discovery"]
    end

    subgraph Download["📥 Stage 2: Download & Version"]
        HEAD["HEAD Request<br/>ETag/LM Check"]
        FETCH["Full Download"]
        HASH["SHA-256<br/>Content Hash"]
        DEDUP["Dedup Check"]
        VERSION["Version Chain<br/>Update"]
        STORE["R2/Local<br/>Storage"]
    end

    subgraph OCR["📄 Stage 3: OCR & Sections"]
        PYMUPDF["PyMuPDF<br/>Fast Path"]
        DOCLING["Docling<br/>Structured Path"]
        QUALITY["Quality<br/>Scoring"]
        SECTIONS["Section<br/>Builder"]
        TABLES["Table<br/>Detection"]
    end

    subgraph Extraction["🤖 Stage 4: LLM Extraction"]
        LLM["LLM Provider<br/>Groq/NVIDIA"]
        SCHEMA["Schema<br/>Validation"]
        CITATION["Citation<br/>Verification"]
        RISK["Risk Event<br/>Extraction"]
        CONSISTENCY["Cross-Section<br/>Consistency"]
    end

    subgraph PostProcess["📊 Stage 5: Post-Processing"]
        NORMALIZE["Risk Event<br/>Normalization"]
        MATRIX["Coverage Matrix<br/>Refresh"]
        CHANGE["Change Event<br/>Generation"]
        METRICS["Quality<br/>Metrics"]
        EMBED["Embedding<br/>Generation"]
    end

    subgraph Storage["💾 Data Stores"]
        PG["PostgreSQL<br/>+ pgvector"]
        R2["Cloudflare R2<br/>Object Storage"]
        REDIS["Redis<br/>Queue + Cache"]
    end

    WEEKLY --> ROBOTS
    DAILY --> HEAD
    MANUAL --> ROBOTS

    ROBOTS --> SITEMAP --> CRAWL
    CRAWL --> PLAYWRIGHT
    CRAWL --> CLASSIFY
    PLAYWRIGHT --> CLASSIFY
    CLASSIFY --> BROCHURE_DISC

    CLASSIFY --> HEAD
    HEAD -->|changed| FETCH
    HEAD -->|unchanged| DEDUP
    FETCH --> HASH --> DEDUP --> VERSION --> STORE

    STORE --> PYMUPDF
    PYMUPDF -->|native text| SECTIONS
    PYMUPDF -->|scanned/complex| DOCLING
    DOCLING --> QUALITY --> SECTIONS
    SECTIONS --> TABLES

    SECTIONS --> LLM
    LLM --> SCHEMA --> CITATION
    CITATION --> RISK
    RISK --> CONSISTENCY

    CONSISTENCY --> NORMALIZE
    NORMALIZE --> MATRIX
    MATRIX --> CHANGE
    CHANGE --> METRICS
    METRICS --> EMBED

    EMBED --> PG
    STORE --> R2
    Scheduler --> REDIS
```

## 2. Data Model (Extended ERD)

```mermaid
erDiagram
    INSURER ||--o{ PRODUCT : offers
    PRODUCT ||--o{ POLICY : "has instances"
    POLICY ||--o{ POLICY_VERSION : versioned
    POLICY_VERSION ||--o{ DOCUMENT : "sourced from"
    POLICY_VERSION ||--o{ SECTION : contains
    POLICY_VERSION ||--o{ RISK_EVENT : "maps to"
    POLICY_VERSION ||--o{ DOCUMENT_COLLECTION : "has brochures"

    SECTION ||--o{ BENEFIT : contains
    SECTION ||--o{ LIMIT : contains
    SECTION ||--o{ EXCLUSION : contains
    SECTION ||--o{ RISK_EVENT : "evidences"

    RISK_AREA ||--o{ RISK_EVENT : categorizes
    RISK_AREA ||--o{ RISK_AREA : "parent/child"

    DOCUMENT_COLLECTION ||--o{ BROCHURE_ASSET : "contains images"

    INSURER ||--o{ PIPELINE_RUN : "crawled by"
    PIPELINE_RUN ||--o{ EXTRACTION_QUALITY_METRIC : measures

    RISK_AREA {
        uuid id PK
        varchar code UK "flood, theft, tpd"
        varchar name
        uuid parent_id FK "nullable hierarchy"
        text description
        int sort_order
    }

    RISK_EVENT {
        uuid id PK
        uuid risk_area_id FK
        uuid policy_version_id FK
        varchar name "Retaining wall collapse"
        varchar coverage_status "covered|excluded|limited|silent"
        text detail
        numeric monetary_limit
        numeric excess_amount
        int waiting_period_days
        uuid document_id FK
        uuid section_id FK
        int page
        float confidence
    }

    DOCUMENT_COLLECTION {
        uuid id PK
        uuid policy_version_id FK
        varchar collection_type "brochure|pds|schedule"
        varchar title
        text source_url
        text storage_key
        char sha256_hash
        int page_count
        date effective_date
        uuid superseded_by_id FK
        boolean is_current
    }

    BROCHURE_ASSET {
        uuid id PK
        uuid document_collection_id FK
        varchar asset_type "cover_image|diagram|table"
        text storage_key
        int page_number
        text caption
        int width_px
        int height_px
    }

    PIPELINE_RUN {
        uuid id PK
        varchar run_type "scheduled|manual|backfill"
        uuid insurer_id FK
        varchar status "pending|running|completed|failed"
        timestamptz started_at
        timestamptz completed_at
        jsonb stats_json
    }

    EXTRACTION_QUALITY_METRIC {
        uuid id PK
        uuid pipeline_run_id FK
        uuid insurer_id FK
        int total_facts_extracted
        int facts_verified
        float verification_rate
        float avg_confidence
        varchar model_used
    }
```

## 3. Weekly Scheduling Timeline

```mermaid
gantt
    title Weekly Pipeline Schedule (Monday NZST)
    dateFormat HH:mm
    axisFormat %H:%M

    section Health
    HEAD check all URLs       :active, health, 02:00, 15min

    section General Insurers
    AMI + State + NZI         :crit, groupA, 02:15, 10min
    Tower + Vero + AA         :crit, groupB, 02:25, 10min
    FMG + MAS + TradeMe       :groupC, 02:35, 10min

    section Life Insurers
    AIA + Partners + Fidelity :groupD, 02:45, 15min

    section Health Insurers
    Southern Cross + nib      :groupE, 03:00, 10min

    section Specialty
    SPCA + Cove + 1Cover      :groupF, 03:10, 10min

    section Post-Processing
    Matrix refresh            :matrix, 03:30, 30min
    Quality report            :quality, 04:00, 15min
    Change digest             :digest, 04:15, 10min
```

## 4. Data Flow: From PDF to Comparison

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant C as Crawler
    participant D as Downloader
    participant O as OCR Engine
    participant L as LLM Provider
    participant V as Verifier
    participant DB as PostgreSQL
    participant M as Matrix

    S->>C: Trigger weekly crawl (Insurer X)
    C->>C: Validate robots.txt
    C->>C: Sitemap + link-follow + Playwright
    C-->>D: DiscoveredDocumentItem queue

    D->>D: HEAD request (ETag check)
    alt Document unchanged
        D-->>S: Skip (log "unchanged")
    else Document new/changed
        D->>D: Download + SHA-256
        D->>DB: Store Document row
        D->>O: Pass content bytes
    end

    O->>O: PyMuPDF (fast) or Docling (structured)
    O->>O: Quality score per page
    O->>DB: Store Section rows (page coords)

    DB->>L: Section text → extraction prompt
    L-->>V: Structured JSON (facts + source_quotes)

    V->>V: Exact substring match
    V->>V: Fuzzy match (≥0.85 threshold)
    alt Citation verified
        V->>DB: Persist fact (Benefit/Limit/Exclusion/RiskEvent)
    else Citation failed
        V->>DB: Log rejection (admin review queue)
    end

    DB->>M: Refresh coverage matrix
    M->>M: JOIN risk_events × insurers × products
    M->>DB: Materialized view updated

    Note over S,DB: Entire flow is idempotent.<br/>Re-running produces identical state.
```

## 5. Coverage Comparison Query Path

```mermaid
flowchart LR
    USER["User: 'Compare flood<br/>cover for house insurance'"]
    API["/api/v1/coverage/matrix<br/>?risk_area=flood&product=house"]
    MV["COVERAGE_MATRIX<br/>(materialized view)"]
    RESULT["Per-insurer results:<br/>AMI: covered, $2M limit<br/>Tower: limited, $500K<br/>State: covered<br/>FMG: excluded"]

    USER --> API --> MV --> RESULT

    style MV fill:#0b6e5a,color:#fff
    style RESULT fill:#f1f2ed,stroke:#12181d
```

## 6. Failure & Recovery State Machine

```mermaid
stateDiagram-v2
    [*] --> Active: Insurer onboarded

    Active --> Degraded: 1-2 consecutive failures
    Active --> Active: Successful weekly run

    Degraded --> Active: Next run succeeds
    Degraded --> Disabled: 3rd consecutive failure

    Active --> Disabled: Verification rate < 50% (2 runs)
    Active --> Disabled: Admin manual block

    Disabled --> Recovery: Admin investigates + fixes
    Recovery --> Active: Test run passes (>85% verification)
    Recovery --> Disabled: Test run fails

    note right of Disabled
        Auto-disabled insurers:
        - Removed from schedule
        - Admin alert sent
        - Last-good data preserved
        - Manual re-enable required
    end note
```
