import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

export interface ScanStatus {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percent: number;
  processed_files: number;
  total_files: number;
  duplicates_found: number;
  near_duplicates_found: number;
  error?: string;
}

export interface DuplicateFile {
  id: string;
  name: string;
  size: number;
  modified_at?: string;
  web_view_link?: string;
  is_flagged: boolean;
}

export interface DuplicateCluster {
  group_id: string;
  type: 'exact' | 'near';
  files: DuplicateFile[];
}

export interface ScanSummary {
  scan_id: string;
  total_files: number;
  duplicates_found: number;
  near_duplicates_found: number;
  total_duplicate_files: number;
  potential_storage_saved_mb: number;
  status: string;
  completed_at?: string;
}

const API_BASE_URL = 'http://localhost:8000';

export function useScan() {
  const [scanId, setScanId] = useState<string | null>(null);
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateCluster[]>([]);
  const [summary, setSummary] = useState<ScanSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create axios instance with base URL
  const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  /**
   * Start a new scan
   */
  const startScan = useCallback(async (userId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await api.post<{ scan_id: string }>(
        '/api/scan/start',
        { user_id: userId }
      );

      const newScanId = response.data.scan_id;
      setScanId(newScanId);

      // Start polling for status
      pollScanStatus(newScanId);

      return newScanId;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to start scan';
      setError(errorMsg);
      console.error('Start scan error:', err);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Get current scan status
   */
  const getScanStatus = useCallback(
    async (id: string) => {
      try {
        const response = await api.get<ScanStatus>(`/api/scan/status/${id}`);
        setStatus(response.data);
        return response.data;
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || 'Failed to get scan status';
        setError(errorMsg);
        console.error('Get status error:', err);
        throw err;
      }
    },
    []
  );

  /**
   * Poll scan status every 1 second until completed or failed
   */
  const pollScanStatus = useCallback(
    (id: string) => {
      const pollInterval = setInterval(async () => {
        try {
          const currentStatus = await getScanStatus(id);

          if (
            currentStatus.status === 'completed' ||
            currentStatus.status === 'failed'
          ) {
            clearInterval(pollInterval);

            // If completed, fetch duplicates and summary
            if (currentStatus.status === 'completed') {
              try {
                await fetchDuplicates(id);
                await fetchSummary(id);
              } catch (err) {
                console.error('Failed to fetch results:', err);
              }
            }
          }
        } catch (err) {
          console.error('Poll error:', err);
          clearInterval(pollInterval);
        }
      }, 1000);

      return pollInterval;
    },
    [getScanStatus]
  );

  /**
   * Get duplicate clusters for a completed scan
   */
  const fetchDuplicates = useCallback(async (id: string) => {
    try {
      const response = await api.get<DuplicateCluster[]>(
        `/api/scan/duplicates/${id}`
      );
      setDuplicates(response.data);
      return response.data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to fetch duplicates';
      setError(errorMsg);
      console.error('Fetch duplicates error:', err);
      throw err;
    }
  }, []);

  /**
   * Get scan summary (storage saved, etc.)
   */
  const fetchSummary = useCallback(async (id: string) => {
    try {
      const response = await api.get<ScanSummary>(
        `/api/scan/summary/${id}`
      );
      setSummary(response.data);
      return response.data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to fetch summary';
      setError(errorMsg);
      console.error('Fetch summary error:', err);
      throw err;
    }
  }, []);

  /**
   * Flag a file as "keep" (not to be deleted)
   */
  const flagFile = useCallback(
    async (fileId: string, keep: boolean = true) => {
      try {
        const response = await api.post(`/api/scan/flag/${fileId}`, {
          keep,
        });

        // Update local duplicates state
        setDuplicates((prev) =>
          prev.map((cluster) => ({
            ...cluster,
            files: cluster.files.map((file) =>
              file.id === fileId ? { ...file, is_flagged: keep } : file
            ),
          }))
        );

        return response.data;
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || 'Failed to flag file';
        setError(errorMsg);
        console.error('Flag file error:', err);
        throw err;
      }
    },
    []
  );

  /**
   * Reset scan state (for starting a new scan)
   */
  const reset = useCallback(() => {
    setScanId(null);
    setStatus(null);
    setDuplicates([]);
    setSummary(null);
    setError(null);
  }, []);

  return {
    // State
    scanId,
    status,
    duplicates,
    summary,
    isLoading,
    error,

    // Methods
    startScan,
    getScanStatus,
    fetchDuplicates,
    fetchSummary,
    flagFile,
    reset,

    // Computed
    isScanning: status?.status === 'running',
    isCompleted: status?.status === 'completed',
    isFailed: status?.status === 'failed',
    progressPercent: status?.progress_percent ?? 0,
  };
}