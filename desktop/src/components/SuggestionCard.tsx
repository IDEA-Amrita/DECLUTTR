import { Trash2, SkipForward, ShieldCheck } from 'lucide-react'
import { FileSuggestion } from '../lib/api'
import { FilePreview } from './FilePreview'

export const TYPE_LABELS: Record<string, string> = {
  duplicate:      'Exact Duplicate',
  near_duplicate: 'Near Duplicate',
  large_file:     'Large File',
  old_file:       'Old File',
  screenshot:     'Screenshot',
}

export const TYPE_COLORS: Record<string, string> = {
  duplicate:      '#FF4D4D',
  near_duplicate: '#F59E0B',
  large_file:     '#7B61FF',
  old_file:       '#8A8A96',
  screenshot:     '#22C55E',
}

export function fmt(bytes: number): string {
  if (bytes > 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`
  if (bytes > 1_048_576)     return `${(bytes / 1_048_576).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

type Props = {
  suggestion: FileSuggestion
  selected: boolean
  onSelect: (id: string, checked: boolean) => void
  onConfirm: (s: FileSuggestion) => void
  onSkip: (id: string) => void
  onProtect: (s: FileSuggestion) => void
}

export function SuggestionCard({ suggestion, selected, onSelect, onConfirm, onSkip, onProtect }: Props) {
  const name = suggestion.path.replace(/\\/g, '/').split('/').pop() ?? suggestion.path
  const color = TYPE_COLORS[suggestion.type] ?? '#8A8A96'
  const confidence = Math.round((suggestion.confidence ?? 0) * 100)

  return (
    <div
      className="group flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
      style={{
        background: selected ? '#7B61FF0D' : 'transparent',
        border: `1px solid ${selected ? '#7B61FF33' : 'transparent'}`,
        cursor: 'default',
      }}
      onMouseEnter={e => {
        if (!selected) (e.currentTarget as HTMLDivElement).style.background = '#ffffff06'
      }}
      onMouseLeave={e => {
        if (!selected) (e.currentTarget as HTMLDivElement).style.background = 'transparent'
      }}
    >
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onChange={e => onSelect(suggestion.id, e.target.checked)}
        className="shrink-0 w-4 h-4 rounded"
        style={{ accentColor: '#7B61FF', cursor: 'pointer' }}
        onClick={e => e.stopPropagation()}
      />

      {/* Preview thumbnail */}
      <div
        className="shrink-0 rounded overflow-hidden"
        style={{ width: 52, height: 52, background: '#1A1A1D', border: '1px solid #2A2A2E' }}
      >
        <FilePreview path={suggestion.path} className="w-full h-full" />
      </div>

      {/* File info */}
      <div className="flex-1 min-w-0 space-y-0.5">
        <p
          className="text-sm font-mono truncate"
          style={{ color: '#F2F2F3' }}
          title={suggestion.path}
        >
          {name}
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono" style={{ color: '#8A8A96' }}>
            {fmt(suggestion.size_bytes)}
          </span>
          {/* Confidence mini-bar */}
          <div className="flex items-center gap-1.5">
            <div
              className="h-1 rounded-full"
              style={{ width: 48, background: '#2A2A2E' }}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${confidence}%`, background: color }}
              />
            </div>
            <span className="text-xs font-mono" style={{ color: '#8A8A96' }}>
              {confidence}%
            </span>
          </div>
        </div>
        {suggestion.reason ? (
          <p
            className="text-xs leading-relaxed truncate"
            style={{ color: '#5A5A66' }}
            title={suggestion.reason}
          >
            {suggestion.reason}
          </p>
        ) : (
          <div
            className="h-2.5 rounded animate-pulse mt-1"
            style={{ background: '#2A2A2E', width: '60%' }}
          />
        )}
      </div>

      {/* Per-file action buttons — visible on group hover */}
      <div
        className="shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <button
          onClick={e => { e.stopPropagation(); onConfirm(suggestion) }}
          className="p-1.5 rounded"
          style={{ background: '#FF4D4D18', color: '#FF4D4D' }}
          title="Delete"
        >
          <Trash2 size={13} />
        </button>
        <button
          onClick={e => { e.stopPropagation(); onSkip(suggestion.id) }}
          className="p-1.5 rounded"
          style={{ background: '#2A2A2E', color: '#8A8A96' }}
          title="Skip"
        >
          <SkipForward size={13} />
        </button>
        <button
          onClick={e => { e.stopPropagation(); onProtect(suggestion) }}
          className="p-1.5 rounded"
          style={{ background: '#7B61FF18', color: '#7B61FF' }}
          title="Protect"
        >
          <ShieldCheck size={13} />
        </button>
      </div>
    </div>
  )
}
