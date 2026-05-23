import { Trash2, SkipForward, ShieldCheck } from 'lucide-react'
import { FileSuggestion } from '../lib/api'
import { ProtectedBadge } from './ProtectedBadge'

const TYPE_LABELS: Record<string, string> = {
  duplicate:      'Exact Duplicate',
  near_duplicate: 'Near Duplicate',
  large_file:     'Large File',
  old_file:       'Old File',
  screenshot:     'Screenshot',
}

const TYPE_COLORS: Record<string, string> = {
  duplicate:      '#FF4D4D',
  near_duplicate: '#F59E0B',
  large_file:     '#7B61FF',
  old_file:       '#8A8A96',
  screenshot:     '#22C55E',
}

function fmt(bytes: number): string {
  if (bytes > 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`
  if (bytes > 1_048_576)     return `${(bytes / 1_048_576).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

type Props = {
  suggestion: FileSuggestion
  onConfirm: (s: FileSuggestion) => void
  onSkip: (id: string) => void
  onProtect: (s: FileSuggestion) => void
}

export function SuggestionCard({ suggestion, onConfirm, onSkip, onProtect }: Props) {
  const name = suggestion.path.replace(/\\/g, '/').split('/').pop() ?? suggestion.path
  const color = TYPE_COLORS[suggestion.type] ?? '#8A8A96'
  const label = TYPE_LABELS[suggestion.type] ?? suggestion.type
  const confidence = Math.round((suggestion.confidence ?? 0) * 100)

  return (
    <div
      className="rounded-xl p-4 space-y-3"
      style={{ background: '#161618', border: '1px solid #2A2A2E' }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-mono truncate" style={{ color: '#F2F2F3' }} title={suggestion.path}>
            {name}
          </p>
          <p className="text-xs font-mono mt-0.5 truncate" style={{ color: '#8A8A96' }}>
            {suggestion.path}
          </p>
        </div>
        <span
          className="shrink-0 text-xs font-mono px-2 py-0.5 rounded"
          style={{ background: color + '22', color, border: `1px solid ${color}44` }}
        >
          {label}
        </span>
      </div>

      <div className="flex items-center gap-3 text-xs font-mono" style={{ color: '#8A8A96' }}>
        <span>{fmt(suggestion.size_bytes)}</span>
        {suggestion.protected === 1 && <ProtectedBadge />}
      </div>

      {suggestion.reason ? (
        <p className="text-xs leading-relaxed" style={{ color: '#8A8A96' }}>
          {suggestion.reason}
        </p>
      ) : (
        <div
          className="h-3 rounded animate-pulse"
          style={{ background: '#2A2A2E', width: '75%' }}
        />
      )}

      <div className="space-y-1">
        <div className="flex justify-between text-xs font-mono" style={{ color: '#8A8A96' }}>
          <span>Confidence</span>
          <span>{confidence}%</span>
        </div>
        <div className="h-1.5 rounded-full" style={{ background: '#2A2A2E' }}>
          <div
            className="h-full rounded-full"
            style={{ width: `${confidence}%`, background: color, transition: 'width 0.4s ease' }}
          />
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onConfirm(suggestion)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
          style={{ background: '#FF4D4D22', color: '#FF4D4D', border: '1px solid #FF4D4D44' }}
        >
          <Trash2 size={12} /> Delete
        </button>
        <button
          onClick={() => onSkip(suggestion.id)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
          style={{ background: '#2A2A2E', color: '#8A8A96' }}
        >
          <SkipForward size={12} /> Skip
        </button>
        <button
          onClick={() => onProtect(suggestion)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-mono"
          style={{ background: '#7B61FF22', color: '#7B61FF', border: '1px solid #7B61FF44' }}
        >
          <ShieldCheck size={12} /> Protect
        </button>
      </div>
    </div>
  )
}
