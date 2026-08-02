import type {
  CompareGeneralRequest,
  CompareGeneralResponse,
  CompareLifeRequest,
  CompareLifeResponse,
  DocumentRecord,
  InsurerCoverage,
  PipelineRun,
  ProductSummary,
  RiskArea,
  RiskEvent,
  SectionText,
} from './types'

// In dev this is relative and hits the Vite proxy (/api -> localhost:8001).
// In the production static build (GitHub Pages) there is no proxy, so the build
// bakes in the absolute backend URL via VITE_API_BASE_URL (see .env.production).
const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  compareLife(filters: CompareLifeRequest): Promise<CompareLifeResponse> {
    return request('/compare/life', {
      method: 'POST',
      body: JSON.stringify(filters),
    })
  },

  compareGeneral(filters: CompareGeneralRequest): Promise<CompareGeneralResponse> {
    return request('/compare/general', {
      method: 'POST',
      body: JSON.stringify(filters),
    })
  },

  async getProducts(): Promise<ProductSummary[]> {
    const res = await request<{ results: ProductSummary[] }>('/products')
    return res.results
  },

  async getInsurerCoverage(): Promise<InsurerCoverage[]> {
    const res = await request<{ results: InsurerCoverage[] }>('/insurers/coverage')
    return res.results
  },

  async getDocuments(): Promise<DocumentRecord[]> {
    return request('/documents')
  },

  async getRiskAreas(): Promise<RiskArea[]> {
    const res = await request<{ areas: RiskArea[]; total: number }>('/risk-areas')
    return res.areas
  },

  async getRiskEvents(areaCode?: string): Promise<RiskEvent[]> {
    const params = areaCode ? `?area_code=${areaCode}` : ''
    const res = await request<{ events: RiskEvent[]; total: number }>(`/risk-events${params}`)
    return res.events
  },

  async getPipelineRuns(limit = 50): Promise<PipelineRun[]> {
    const res = await request<{ runs: PipelineRun[]; total: number }>(`/pipeline/runs?limit=${limit}`)
    return res.runs
  },

  /** Fetch the full extracted source text for a document page (citation "view source"). */
  getSectionText(documentId: string, page: number): Promise<SectionText> {
    return request(`/documents/${documentId}/pages/${page}`)
  },
}
