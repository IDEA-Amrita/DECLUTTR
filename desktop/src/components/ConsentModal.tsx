import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { FileSuggestion } from '../lib/api'
import { fmt } from './SuggestionCard'

type Props = {
  // Pass a single item OR a batch
  suggestions: FileSuggestion[]
  open: boolean
  onConfirm: (items: FileSuggestion[]) => void
  onCancel: () => void
}

export function ConsentModal({ suggestions, open, onConfirm, onCancel }: Props) {
  const [checked, setChecked] = useState(false)

  if (!open || suggestions.length === 0) return null

  const isBatch = suggestions.length > 1
  const totalBytes = suggestions.reduce((s, x) => s + x.size_bytes, 0)
  const SHOW_MAX = 6

  const handleConfirm = () => {
    onConfirm(suggestions)
    setChecked(false)
  }

  const handleCancel = () => {
    setChecked(false)
    onCancel()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.82)' }}
      onClick={handleCancel}
    >
      <div
        className="rounded-2xl p-6 w-[480px] space-y-5"
        style={{ background: '#161618', border: '1px solid #2A2A2E', boxShadow: '0 24px 80px rgba(0,0,0,0.6)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-3">
          <div
            className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ background: '#FF4D4D18' }}
          >
            <AlertTriangle size={18} style={{ color: '#FF4D4D' }} />
          </div>
          <div>
            <h2 className="font-serif text-lg" style={{ color: '#F2F2F3' }}>
              {isBatch ? `Move ${suggestions.length} files to Recycle Bin` : 'Confirm deletion'}
            </h2>
            <p className="text-xs font-mono mt-0.5" style={{ color: '#8A8A96' }}>
              {isBatch
                ? `${fmt(totalBytes)} will be freed`
                : suggestions[0].path.replace(/\\/g, '/').split('/').pop()}
            </p>
          </div>
        </div>

        {/* File list (batch) */}
        {isBatch && (
          <div
            className="rounded-lg divide-y divide-[#2A2A2E] overflow-hidden"
            style={{ border: '1px solid #2A2A2E' }}
          >
            {suggestions.slice(0, SHOW_MAX).map(s => (
              <div
                key={s.id}
                className="flex items-center justify-between px-3 py-2"
                style={{ background: '#0D0D0F' }}
              >
                <span
                  className="text-xs font-mono truncate"
                  style={{ color: '#F2F2F3', maxWidth: '80%' }}
                  title={s.path}
                >
                  {s.path.replace(/\\/g, '/').split('/').pop()}
                </span>
                <span className="text-xs font-mono shrink-0 ml-2" style={{ color: '#8A8A96' }}>
                  {fmt(s.size_bytes)}
                </span>
              </div>
            ))}
            {suggestions.length > SHOW_MAX && (
              <div
                className="px-3 py-2 text-xs font-mono text-center"
                style={{ background: '#0D0D0F', color: '#8A8A96' }}
              >
                +{suggestions.length - SHOW_MAX} more files
              </div>
            )}
          </div>
        )}

        {/* Consent checkbox */}
        <label
          className="flex items-center gap-2.5 text-sm font-mono cursor-pointer select-none"
          style={{ color: '#8A8A96' }}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={e => setChecked(e.target.checked)}
            style={{ accentColor: '#FF4D4D', width: 16, height: 16, cursor: 'pointer' }}
          />
          I understand — move {isBatch ? `these ${suggestions.length} files` : 'this file'} to the Recycle Bin
        </label>

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm rounded-lg font-mono"
            style={{ background: '#2A2A2E', color: '#8A8A96' }}
          >
            Cancel
          </button>
          <button
            disabled={!checked}
            onClick={handleConfirm}
            className="px-4 py-2 text-sm rounded-lg font-mono transition-all"
            style={{
              background: checked ? '#FF4D4D' : '#2A2A2E',
              color: '#fff',
              opacity: checked ? 1 : 0.35,
              cursor: checked ? 'pointer' : 'not-allowed',
            }}
          >
            Move to Recycle Bin
          </button>
        </div>
      </div>
    </div>
  )
}
