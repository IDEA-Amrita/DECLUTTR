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

// ── Google Drive (Phase 2) ─────────────────────────────────────────────────
export type DriveAuthStatus = {
  linked: boolean
  email: string | null
  accounts: { id: number; email: string }[]
}

export type DriveScanStatus = {
  scan_id: string
  status: string
  phase: string | null
  progress: number
  total_files: number
  processed_files: number
  duplicates_found: number
  clusters_found: number
  deletion_candidates: number
  bytes_reclaimable: number
  error_message: string | null
}

export type DriveFile = {
  id: number
  drive_id: string
  name: string
  mime_type: string
  size_bytes: number
  category: string | null
  confidence: number
  duplicate_group_id: string | null
  is_cluster_original: boolean
  ai_reason: string | null
  user_flag: string | null
  user_description: string | null
  is_protected: boolean
  in_deletion_list: boolean
  deletion_bucket: string | null
  thumbnail_link: string | null
  web_view_link: string | null
  target_folder_path: string | null
  modified_at: string | null
}

export type DriveCluster = {
  group_id: string
  count: number
  total_bytes: number
  files: DriveFile[]
}

export type DriveDeletionBucket = {
  key: string
  label: string
  count: number
  total_bytes: number
  files: DriveFile[]
}

export type DriveDeletionList = {
  total_files: number
  total_bytes: number
  avg_confidence: number
  buckets: DriveDeletionBucket[]
  excluded: { described: number; protected: number; recent: number }
}

export type DriveOrganisePlan = {
  paradigms: string[]
  folders: { path: string; count: number }[]
  files_planned: number
}

export type DriveCompressionCandidate = {
  record_id: number
  name: string
  original_size: number
  estimated_size: number
  compression_type: string
  savings_pct: number
}

export type DriveCompression = {
  candidates: DriveCompressionCandidate[]
  count: number
  original_bytes: number
  estimated_bytes: number
  savings_bytes: number
}

export type DriveExecuteReport = {
  deleted: number
  moved: number
  folders_created: number
  compressed_queued: number
  protected: number
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

  // Google Drive (Phase 2)
  getDriveAuthStatus: () =>
    request<DriveAuthStatus>('/gdrive/auth/status'),

  getDriveAuthUrl: () =>
    request<{ auth_url: string }>('/gdrive/auth/url'),

  unlinkDrive: () =>
    request<{ unlinked: boolean }>('/gdrive/auth/unlink', { method: 'DELETE' }),

  startDriveScan: () =>
    request<{ scan_id: string }>('/gdrive/scan', { method: 'POST' }),

  getDriveScanStatus: (id: string) =>
    request<DriveScanStatus>(`/gdrive/scan/${id}/status`),

  getDriveFiles: (id: string) =>
    request<DriveFile[]>(`/gdrive/scan/${id}/files`),

  getDriveClusters: (id: string) =>
    request<{ clusters: DriveCluster[]; cluster_count: number }>(`/gdrive/scan/${id}/clusters`),

  keepDriveFile: (
    id: string,
    body: { record_id: number; description?: string; flag?: string; location_tag?: string },
  ) =>
    request<{ record_id: number; protected: boolean; moved_to_deletion: number }>(
      `/gdrive/scan/${id}/keep`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  organiseDrive: (id: string, paradigms: string[]) =>
    request<DriveOrganisePlan>(`/gdrive/scan/${id}/organise`, {
      method: 'POST', body: JSON.stringify({ paradigms }),
    }),

  getDriveCompression: (id: string) =>
    request<DriveCompression>(`/gdrive/scan/${id}/compression`),

  getDriveDeletionList: (id: string) =>
    request<DriveDeletionList>(`/gdrive/scan/${id}/deletion-list`),

  toggleDriveDeletion: (id: string, record_id: number, in_deletion_list: boolean) =>
    request<{ record_id: number; in_deletion_list: boolean }>(
      `/gdrive/scan/${id}/deletion-list/toggle`,
      { method: 'POST', body: JSON.stringify({ record_id, in_deletion_list }) },
    ),

  executeDriveCleanup: (
    id: string,
    body: { do_delete: boolean; do_organize: boolean; do_compress: boolean },
  ) =>
    request<DriveExecuteReport>(`/gdrive/scan/${id}/execute`, {
      method: 'POST', body: JSON.stringify(body),
    }),

  undoDriveCleanup: (id: string) =>
    request<{ restored: number; moved_back: number }>(`/gdrive/scan/${id}/undo`, {
      method: 'POST',
    }),
}
