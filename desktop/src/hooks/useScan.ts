/**
 * Thin hook wrapper around useScanStore.
 * Keeps the same public shape ({status, progress, suggestions, scanId,
 * error, startScan}) so callers don't need to change.
 *
 * State now lives in a Zustand store, so navigating away from StoragePage
 * and coming back preserves a running scan and its results.
 */
import { useScanStore } from '../store/scanStore'

export type { ScanStatus } from '../store/scanStore'

export function useScan() {
  const {
    status, progress, suggestions, scanId, error, startScan,
  } = useScanStore()

  return { status, progress, suggestions, scanId, error, startScan }
}
