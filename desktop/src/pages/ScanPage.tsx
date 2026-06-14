import React, { useState } from 'react';
import { useScan } from '../hooks/useScan';

export function ScanPage() {
  const {
    scanId,
    status,
    duplicates,
    summary,
    isLoading,
    error,
    startScan,
    flagFile,
    reset,
    isScanning,
    isCompleted,
    isFailed,
    progressPercent,
  } = useScan();

  const [userId] = useState('test-user-1');
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);

  const handleStartScan = async () => {
    try {
      await startScan(userId);
    } catch (err) {
      console.error('Failed to start scan:', err);
    }
  };

  const handleFlagFile = async (fileId: string) => {
    try {
      await flagFile(fileId, true);
    } catch (err) {
      console.error('Failed to flag file:', err);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl font-bold mb-2">Google Drive Cleanup</h1>
          <p className="text-gray-400">Privacy-first cloud declutter</p>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-500 rounded-lg p-4 mb-8">
            <p className="text-red-300 font-semibold">Error</p>
            <p className="text-red-200 text-sm">{error}</p>
          </div>
        )}

        {/* Phase 1: Start Scan */}
        {!scanId && (
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-8 mb-8">
            <div className="flex items-start gap-4">
              <div className="bg-blue-600 rounded-full w-10 h-10 flex items-center justify-center flex-shrink-0 font-bold">
                1
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-2">Scan your Drive</h2>
                <p className="text-gray-400 mb-6">
                  We'll securely analyze your Google Drive to find duplicate and similar files.
                  <br />
                  Only file names, sizes, and metadata are processed. No content is downloaded.
                </p>
                <button
                  onClick={handleStartScan}
                  disabled={isLoading}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed px-6 py-3 rounded-lg font-semibold transition-colors"
                >
                  {isLoading ? 'Starting...' : 'Start scan'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Phase 2: Scanning Progress */}
        {isScanning && status && (
          <div className="bg-gray-800 border border-blue-600 rounded-lg p-8 mb-8">
            <div className="flex items-start gap-4">
              <div className="bg-blue-600 rounded-full w-10 h-10 flex items-center justify-center flex-shrink-0 font-bold animate-spin">
                ⟳
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-4">Scanning your Drive</h2>

                {/* Progress Bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm text-gray-400 mb-2">
                    <span>Progress</span>
                    <span>{Math.round(progressPercent)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-blue-600 h-full transition-all duration-300 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-400">Files processed</p>
                    <p className="text-lg font-semibold">
                      {status.processed_files} / {status.total_files}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400">Duplicates found</p>
                    <p className="text-lg font-semibold text-amber-400">
                      {status.duplicates_found}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Phase 3: Review Duplicates */}
        {isCompleted && status && duplicates.length > 0 && (
          <div className="bg-gray-800 border border-green-600 rounded-lg p-8 mb-8">
            <div className="flex items-start gap-4 mb-8">
              <div className="bg-green-600 rounded-full w-10 h-10 flex items-center justify-center flex-shrink-0 font-bold">
                2
              </div>
              <div className="flex-1">
                <h2 className="text-2xl font-bold">Review & flag</h2>
                <p className="text-gray-400 text-sm">
                  Keep one file per group, rest will be deleted
                </p>
              </div>
            </div>

            {/* Summary Stats */}
            {summary && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Duplicate groups</p>
                  <p className="text-2xl font-bold">{duplicates.length}</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Total duplicates</p>
                  <p className="text-2xl font-bold">{summary.total_duplicate_files}</p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Can reclaim</p>
                  <p className="text-2xl font-bold text-green-400">
                    {Math.round(summary.potential_storage_saved_mb)} MB
                  </p>
                </div>
                <div className="bg-gray-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm">Status</p>
                  <p className="text-lg font-bold text-green-400">Ready</p>
                </div>
              </div>
            )}

            {/* Duplicate Clusters */}
            <div className="space-y-4">
              {duplicates.map((cluster) => (
                <div key={cluster.group_id} className="border border-gray-700 rounded-lg overflow-hidden">
                  {/* Cluster Header */}
                  <button
                    onClick={() =>
                      setExpandedCluster(
                        expandedCluster === cluster.group_id ? null : cluster.group_id
                      )
                    }
                    className="w-full bg-gray-700 hover:bg-gray-600 p-4 flex items-center justify-between transition-colors"
                  >
                    <div className="flex items-center gap-3 text-left flex-1">
                      <div className="text-sm font-semibold">
                        {cluster.type === 'exact' ? 'Exact Match' : 'Similar Files'}
                      </div>
                      <div className="text-gray-400 text-sm">
                        {cluster.files.length} files •{' '}
                        {formatBytes(
                          cluster.files.reduce((sum, f) => sum + f.size, 0)
                        )}
                      </div>
                    </div>
                    <span className="text-gray-400">
                      {expandedCluster === cluster.group_id ? '▼' : '▶'}
                    </span>
                  </button>

                  {/* Expanded Files List */}
                  {expandedCluster === cluster.group_id && (
                    <div className="bg-gray-800 p-4 space-y-3">
                      {cluster.files.map((file) => (
                        <div
                          key={file.id}
                          className="flex items-center justify-between p-3 bg-gray-700 rounded-lg"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate text-sm">{file.name}</p>
                            <p className="text-xs text-gray-400">
                              {formatBytes(file.size)} • Modified{' '}
                              {formatDate(file.modified_at)}
                            </p>
                          </div>
                          {!file.is_flagged && (
                            <button
                              onClick={() => handleFlagFile(file.id)}
                              className="ml-4 bg-green-600 hover:bg-green-700 px-3 py-1 rounded text-sm font-semibold transition-colors flex-shrink-0"
                            >
                              Keep
                            </button>
                          )}
                          {file.is_flagged && (
                            <div className="ml-4 bg-green-900/30 border border-green-600 text-green-400 px-3 py-1 rounded text-sm font-semibold flex-shrink-0">
                              ✓ Keeping
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Next Steps */}
            <div className="mt-8 pt-8 border-t border-gray-700">
              <p className="text-sm text-gray-400 mb-4">
                Once you've reviewed all clusters, proceed to delete marked duplicates.
              </p>
              <button
                onClick={reset}
                className="w-full bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold transition-colors"
              >
                Next: Organize files
              </button>
            </div>
          </div>
        )}

        {/* No Duplicates Found */}
        {isCompleted && status && duplicates.length === 0 && (
          <div className="bg-gray-800 border border-green-600 rounded-lg p-8">
            <div className="text-center">
              <p className="text-3xl mb-4">✨</p>
              <h2 className="text-2xl font-bold mb-2">No duplicates found</h2>
              <p className="text-gray-400 mb-6">
                Your Drive is clean! {status.total_files} files scanned, all unique.
              </p>
              <button
                onClick={reset}
                className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold transition-colors"
              >
                Scan again
              </button>
            </div>
          </div>
        )}

        {/* Scan Failed */}
        {isFailed && status?.error && (
          <div className="bg-red-900/30 border border-red-600 rounded-lg p-8">
            <div className="flex items-start gap-4">
              <p className="text-3xl">⚠</p>
              <div className="flex-1">
                <h2 className="text-2xl font-bold mb-2">Scan failed</h2>
                <p className="text-red-200 mb-6">{status.error}</p>
                <button
                  onClick={reset}
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold transition-colors"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ScanPage;