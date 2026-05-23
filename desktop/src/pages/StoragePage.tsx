import { useState, useEffect } from 'react'
import { FolderOpen, Loader2 } from 'lucide-react'
import { useScan } from '../hooks/useScan'
import { useConsent } from '../hooks/useConsent'
import { SuggestionCard } from '../components/SuggestionCard'
import { ConsentModal } from '../components/ConsentModal'
import { api, FileSuggestion } from '../lib/api'

export function StoragePage() {
  const { status, progress, suggestions: rawSuggestions, startScan, error } = useScan()
  const [suggestions, setSuggestions] = useState<FileSuggestion[]>([])
  const [modalTarget, setModalTarget] = useState<FileSuggestion | null>(null)
  const { confirm, skip } = useConsent(setSuggestions)

  // sync rawSuggestions → local state when scan completes
  useEffect(() => {
    if (rawSuggestions.length > 0) {
      setSuggestions(rawSuggestions)
    }
  }, [rawSuggestions])

  const pickDir = async () => {
    const dir = window.electron?.openDirectory
      ? await window.electron.openDirectory()
      : prompt('Enter directory path (Electron not running):')
    if (dir) {
      setSuggestions([])
      startScan(dir)
    }
  }

  const handleProtect = async (s: FileSuggestion) => {
    const name = s.path.replace(/\\/g, '/').split('/').pop() ?? s.path
    await api.addProtectedRule('path', s.path, name)
    setSuggestions(prev => prev.filter(x => x.id !== s.id))
  }

  const handleConfirm = async (s: FileSuggestion) => {
    setModalTarget(null)
    await confirm(s)
  }

  const isScanning = status === 'scanning' || status === 'generating_reasons'

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <h1 className="font-serif text-2xl" style={{ color: '#F2F2F3' }}>Storage Scanner</h1>

      <button
        onClick={pickDir}
        disabled={isScanning}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono disabled:opacity-50"
        style={{ background: '#7B61FF', color: '#fff' }}
      >
        <FolderOpen size={16} /> Choose Directory
      </button>

      {isScanning && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-mono" style={{ color: '#8A8A96' }}>
            <Loader2 size={14} className="animate-spin" />
            {status === 'scanning' ? 'Scanning files…' : 'Generating AI reasons…'}
          </div>
          <div className="h-1.5 rounded-full" style={{ background: '#2A2A2E' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: '#7B61FF' }}
            />
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm font-mono" style={{ color: '#FF4D4D' }}>{error}</p>
      )}

      {suggestions.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-sm" style={{ color: '#8A8A96' }}>
              {suggestions.length} suggestion{suggestions.length !== 1 ? 's' : ''}
            </p>
            <button
              onClick={() => setSuggestions([])}
              className="text-xs font-mono px-3 py-1 rounded"
              style={{ background: '#2A2A2E', color: '#8A8A96' }}
            >
              Skip All
            </button>
          </div>
          {suggestions.map(s => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              onConfirm={() => setModalTarget(s)}
              onSkip={skip}
              onProtect={handleProtect}
            />
          ))}
        </div>
      )}

      {status === 'complete' && suggestions.length === 0 && (
        <p className="font-mono text-sm" style={{ color: '#22C55E' }}>
          No clutter found — or all items cleared.
        </p>
      )}

      <ConsentModal
        suggestion={modalTarget}
        open={!!modalTarget}
        onConfirm={handleConfirm}
        onCancel={() => setModalTarget(null)}
      />
    </div>
  )
}
