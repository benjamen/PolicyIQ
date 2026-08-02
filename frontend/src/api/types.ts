/** Shared API types matching backend schemas */

export type CoverageStatus = 'covered' | 'excluded' | 'limited' | 'sub_limited' | 'silent'

export type FactCategory = 'benefit' | 'limit' | 'exclusion'

/** Citation provenance for an extracted fact. Matches backend SourceRefOut. */
export interface SourceRef {
  insurer: string
  document: string
  page: number
  paragraph_ref: string
  confidence: number
  document_id: string | null
}

/** Full extracted source text for a document page (backs "view source"). */
export interface SectionText {
  document_id: string
  page: number
  text: string
}

export interface GeneralInsuranceFact {
  category: FactCategory
  name: string
  detail: string | null
  source: SourceRef | null
}

/** Grading scores are on a 0-100 scale from the backend. */
export interface CriterionOut {
  score: number | null
  weight: number
  raw_value: string
  source: SourceRef | null
  /** Plain-English explanation of why this score was assigned. */
  rationale: string
}

export interface GradeReport {
  insurer: string
  product_name: string
  policy_version_id: string
  eligible: boolean
  ineligibility_reason: string | null
  overall_score: number | null
  data_completeness: number
  criteria: Record<string, CriterionOut>
  exclusions: GeneralInsuranceFact[]
}

export interface CompareLifeRequest {
  age: number
  smoker_status: 'non_smoker' | 'smoker'
  occupation_category: string
  product_type: string
}

export interface CompareLifeResponse {
  filters: CompareLifeRequest
  results: GradeReport[]
  data_source: string
}

export interface GeneralProductProfile {
  insurer: string
  product_name: string
  policy_version_id: string
  facts: GeneralInsuranceFact[]
}

export interface CompareGeneralRequest {
  product_type: string
}

export interface CompareGeneralResponse {
  filters: CompareGeneralRequest
  results: GeneralProductProfile[]
  data_source: string
}

/** Aggregate stats for a general-insurance profile, computed client-side. */
export interface ProfileStats {
  benefits: number
  limits: number
  exclusions: number
  totalLimitValue: number
}

export interface InsurerCoverageType {
  product_type: string
  offered: boolean
  covered: boolean
}

export interface InsurerCoverage {
  name: string
  website: string
  notes: string | null
  types: InsurerCoverageType[]
}

/** One row of the Products tab's flat, cross-category product catalog. */
export interface ProductSummary {
  insurer: string
  product_name: string
  product_type: string
  policy_version_id: string
  kind: 'life' | 'general'
  fact_count: number
}

export interface RiskArea {
  code: string
  name: string
  parent_code: string | null
  description: string | null
  sort_order: number
  children?: RiskArea[]
}

export interface RiskEvent {
  id: string
  area_code: string
  name: string
  description: string | null
  coverage_by_insurer: Record<string, CoverageStatus>
}

export interface PipelineRun {
  id: string
  insurer: string
  status: 'running' | 'completed' | 'failed' | 'partial'
  started_at: string
  finished_at: string | null
  documents_found: number
  documents_new: number
  extractions_ok: number
  extractions_failed: number
  error_message: string | null
}

export interface DocumentRecord {
  id: string
  insurer: string
  product_type: string
  title: string
  source_url: string
  sha256: string
  downloaded_at: string
  page_count: number | null
  is_brochure: boolean
}
