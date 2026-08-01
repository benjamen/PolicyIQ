/** Shared API types matching backend schemas */

export type CoverageStatus = 'covered' | 'excluded' | 'limited' | 'sub_limited' | 'silent'

export interface SourceRef {
  document_id: string
  page: number | null
  quote: string
  verified: boolean
}

export interface GeneralInsuranceFact {
  category: string
  name: string
  detail: string
  source: SourceRef | null
}

export interface CriterionOut {
  score: number
  weight: number
  raw_value: string
  source: SourceRef | null
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

export interface InsurerCoverageType {
  product_type: string
  covered: boolean
  document_count: number
}

export interface InsurerCoverage {
  name: string
  types: InsurerCoverageType[]
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
