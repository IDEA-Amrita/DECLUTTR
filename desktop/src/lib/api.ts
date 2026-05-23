const BASE = 'http://localhost:8000/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json()
}

export type FileSuggestion = {
  id: string; scan_id: string; type: string; path: string
  size_bytes: number; last_accessed: number; reason: string | null
  confidence: number | null; action: string
  consent_given: number; skipped: number; protected: number
}

export type ScanStatus = { status: string; progress: number }

export type ProtectedRule = {
  id: string; type: string; value: string; label: string; created_at: string
}

export type PhotoScore = {
  path: string; score: number; sharpness: number
  brightness: number; composition: number; reason: string | null
}

export type WeeklySnapshot = {
  id: string; week_start: string; storage_score: number
  photo_score: number; composite_score: number
  mb_reclaimed: number; items_cleared: number
}

export const api = {
  health: () =>
    request<{ status: string }>('/health'),

  startScan: (directory: string) =>
    request<{ scan_id: string }>('/storage/scan', {
      method: 'POST', body: JSON.stringify({ directory }),
    }),

  getScanStatus: (id: string) =>
    request<ScanStatus>(`/storage/scan/${id}/status`),

  getSuggestions: (id: string) =>
    request<FileSuggestion[]>(`/storage/scan/${id}/suggestions`),

  confirmConsent: (suggestion_id: string, module: string, action: string, confirmed: boolean) =>
    request<{ executed: boolean }>('/consent/confirm', {
      method: 'POST',
      body: JSON.stringify({ suggestion_id, module, action, confirmed }),
    }),

  getProtectedRules: () =>
    request<ProtectedRule[]>('/protected/rules'),

  addProtectedRule: (type: string, value: string, label: string) =>
    request<ProtectedRule>('/protected/rules', {
      method: 'POST', body: JSON.stringify({ type, value, label }),
    }),

  deleteProtectedRule: (id: string) =>
    request<{ deleted: boolean }>(`/protected/rules/${id}`, { method: 'DELETE' }),

  startPhotoScore: (directory: string) =>
    request<{ job_id: string }>('/photos/score', {
      method: 'POST', body: JSON.stringify({ directory }),
    }),

  getPhotoStatus: (id: string) =>
    request<{ status: string }>(`/photos/score/${id}/status`),

  getTopPhotos: (id: string) =>
    request<PhotoScore[]>(`/photos/score/${id}/top`),

  getWeeklyReport: () =>
    request<WeeklySnapshot[]>('/report/weekly'),

  createSnapshot: () =>
    request<WeeklySnapshot>('/report/snapshot', { method: 'POST' }),
}
