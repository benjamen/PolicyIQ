import type {
  CompareGeneralRequest,
  CompareGeneralResponse,
  CompareLifeRequest,
  CompareLifeResponse,
  DocumentRecord,
  InsurerCoverage,
  PipelineRun,
  RiskArea,
  RiskEvent,
} from './types'

const BASE = '/api/v1'

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

  getInsurerCoverage(): Promise<InsurerCoverage[]> {
    return request('/insurers/coverage')
  },

  getDocuments(): Promise<DocumentRecord[]> {
    return request('/documents')
  },

  getRiskAreas(): Promise<RiskArea[]> {
    return request('/risk-areas')
  },

  getRiskEvents(areaCode?: string): Promise<RiskEvent[]> {
    const params = areaCode ? `?area_code=${areaCode}` : ''
    return request(`/risk-events${params}`)
  },

  getPipelineRuns(limit = 50): Promise<PipelineRun[]> {
    return request(`/pipeline/runs?limit=${limit}`)
  },
}
