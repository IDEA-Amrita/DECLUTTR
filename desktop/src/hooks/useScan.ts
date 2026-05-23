import { useState, useRef, useCallback } from 'react'
import { api, FileSuggestion } from '../lib/api'

export type ScanState = {
  status: 'idle' | 'scanning' | 'generating_reasons' | 'complete' | 'error'
  progress: number
  suggestions: FileSuggestion[]
  scanId: string | null
  error: string | null
}

export function useScan() {
  const [state, setState] = useState<ScanState>({
    status: 'idle', progress: 0, suggestions: [], scanId: null, error: null,
  })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startScan = useCallback(async (directory: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    setState({ status: 'scanning', progress: 0, suggestions: [], scanId: null, error: null })

    try {
      const { scan_id } = await api.startScan(directory)
      setState(s => ({ ...s, scanId: scan_id }))

      pollRef.current = setInterval(async () => {
        try {
          const { status, progress } = await api.getScanStatus(scan_id)
          setState(s => ({ ...s, status: status as ScanState['status'], progress }))

          if (status === 'complete') {
            clearInterval(pollRef.current!)
            const suggestions = await api.getSuggestions(scan_id)
            setState(s => ({ ...s, suggestions }))
          } else if (status === 'error') {
            clearInterval(pollRef.current!)
            setState(s => ({ ...s, error: 'Scan failed on the backend.' }))
          }
        } catch (e) {
          clearInterval(pollRef.current!)
          setState(s => ({ ...s, status: 'error', error: String(e) }))
        }
      }, 2000)
    } catch (e) {
      setState(s => ({ ...s, status: 'error', error: String(e) }))
    }
  }, [])

  return { ...state, startScan }
}
