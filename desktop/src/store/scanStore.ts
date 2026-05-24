/**
 * Global scan store — survives route changes.
 *
 * All scan lifecycle state (status, progress, suggestions, selection)
 * lives here so that navigating to Photos / Report / Home and back to
 * Storage never loses an in-progress scan or its results.
 */
import { create } from 'zustand'
import { api, FileSuggestion } from '../lib/api'

export type ScanStatus =
  | 'idle'
  | 'scanning'
  | 'generating_reasons'
  | 'complete'
  | 'error'

type ScanStore = {
  // ── scan lifecycle ─────────────────────────────────────────────────
  status:    ScanStatus
  progress:  number
  scanId:    string | null
  error:     string | null

  // ── results + selection (persist across navigation) ────────────────
  suggestions: FileSuggestion[]
  selectedIds: Set<string>

  // ── internal: not reactive, just for cleanup ───────────────────────
  _poll: ReturnType<typeof setInterval> | null

  // ── actions ────────────────────────────────────────────────────────
  startScan:      (directory: string) => Promise<void>
  /** Accept a new value OR a functional updater — mirrors React setState. */
  setSuggestions: (action: FileSuggestion[] | ((p: FileSuggestion[]) => FileSuggestion[])) => void
  /** Accept a new Set OR a functional updater — mirrors React setState. */
  setSelectedIds: (action: Set<string> | ((p: Set<string>) => Set<string>)) => void
  clearScan:      () => void
}

export const useScanStore = create<ScanStore>((set, get) => ({
  status:      'idle',
  progress:    0,
  scanId:      null,
  error:       null,
  suggestions: [],
  selectedIds: new Set(),
  _poll:       null,

  // ── startScan ───────────────────────────────────────────────────────
  startScan: async (directory: string) => {
    // Cancel any running poll first
    const existing = get()._poll
    if (existing) clearInterval(existing)

    set({
      status:      'scanning',
      progress:    0,
      scanId:      null,
      error:       null,
      suggestions: [],
      selectedIds: new Set(),
      _poll:       null,
    })

    try {
      const { scan_id } = await api.startScan(directory)
      set({ scanId: scan_id })

      const poll = setInterval(async () => {
        try {
          const { status, progress } = await api.getScanStatus(scan_id)
          set({ status: status as ScanStatus, progress })

          if (status === 'complete') {
            clearInterval(poll)
            set({ _poll: null })
            const suggestions = await api.getSuggestions(scan_id)
            set({ suggestions })
          } else if (status === 'error') {
            clearInterval(poll)
            set({ _poll: null, error: 'Scan failed on the backend.' })
          }
        } catch (e) {
          clearInterval(poll)
          set({ _poll: null, status: 'error', error: String(e) })
        }
      }, 2000)

      set({ _poll: poll })
    } catch (e) {
      set({ status: 'error', error: String(e) })
    }
  },

  // ── setSuggestions ──────────────────────────────────────────────────
  setSuggestions: (action) => {
    if (typeof action === 'function') {
      set(state => ({ suggestions: action(state.suggestions) }))
    } else {
      set({ suggestions: action })
    }
  },

  // ── setSelectedIds ──────────────────────────────────────────────────
  setSelectedIds: (action) => {
    if (typeof action === 'function') {
      set(state => ({ selectedIds: action(state.selectedIds) }))
    } else {
      set({ selectedIds: action })
    }
  },

  // ── clearScan ───────────────────────────────────────────────────────
  clearScan: () => {
    const poll = get()._poll
    if (poll) clearInterval(poll)
    set({
      status: 'idle', progress: 0, scanId: null, error: null,
      suggestions: [], selectedIds: new Set(), _poll: null,
    })
  },
}))
