import { useState } from 'react'
import { FileSuggestion } from '../lib/api'

type Props = {
  suggestion: FileSuggestion | null
  open: boolean
  onConfirm: (s: FileSuggestion) => void
  onCancel: () => void
}

export function ConsentModal({ suggestion, open, onConfirm, onCancel }: Props) {
  const [checked, setChecked] = useState(false)

  if (!open || !suggestion) return null
  const name = suggestion.path.replace(/\\/g, '/').split('/').pop() ?? suggestion.path

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.75)' }}
      onClick={onCancel}
    >
      <div
        className="rounded-xl p-6 w-[440px] space-y-4"
        style={{ background: '#161618', border: '1px solid #2A2A2E' }}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="font-serif text-lg" style={{ color: '#F2F2F3' }}>Confirm deletion</h2>
        <p className="text-sm font-mono" style={{ color: '#8A8A96' }}>
          This will move{' '}
          <span style={{ color: '#F2F2F3', fontWeight: 500 }}>{name}</span>{' '}
          to the Recycle Bin.
        </p>
        <label className="flex items-center gap-2 text-sm font-mono cursor-pointer" style={{ color: '#8A8A96' }}>
          <input
            type="checkbox"
            checked={checked}
            onChange={e => setChecked(e.target.checked)}
            className="accent-accent"
          />
          I understand this action
        </label>
        <div className="flex gap-3 justify-end pt-1">
          <button
            onClick={() => { setChecked(false); onCancel() }}
            className="px-4 py-2 text-sm rounded-lg font-mono"
            style={{ background: '#2A2A2E', color: '#8A8A96' }}
          >
            Cancel
          </button>
          <button
            disabled={!checked}
            onClick={() => { onConfirm(suggestion); setChecked(false) }}
            className="px-4 py-2 text-sm rounded-lg font-mono transition-colors"
            style={{
              background: checked ? '#FF4D4D' : '#2A2A2E',
              color: '#fff',
              opacity: checked ? 1 : 0.4,
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
