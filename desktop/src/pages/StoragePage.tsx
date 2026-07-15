import { useState, useMemo } from 'react'
import {
  FolderOpen, Loader2, Trash2, SkipForward, ShieldCheck,
  ChevronDown, ChevronRight, Camera, Copy, HardDrive, Clock, FileImage,
} from 'lucide-react'
import { useScanStore } from '../store/scanStore'
import { useConsent } from '../hooks/useConsent'
import { SuggestionCard, TYPE_LABELS, TYPE_COLORS, fmt } from '../components/SuggestionCard'
import { ConsentModal } from '../components/ConsentModal'
import { api, FileSuggestion } from '../lib/api'

// ─── Group metadata ──────────────────────────────────────────────────────────

const TYPE_ICONS: Record<string, React.ComponentType<{ size?: number; style?: React.CSSProperties }>> = {
  screenshot:     Camera,
  duplicate:      Copy,
  near_duplicate: Copy,
  large_file:     HardDrive,
  old_file:       Clock,
}

function getGroupIcon(type: string) {
  const Icon = TYPE_ICONS[type] ?? FileImage
  return Icon
}

// ─── Helper ──────────────────────────────────────────────────────────────────

function groupSuggestions(items: FileSuggestion[]): Record<string, FileSuggestion[]> {
  const groups: Record<string, FileSuggestion[]> = {}
  for (const item of items) {
    if (!groups[item.type]) groups[item.type] = []
    groups[item.type].push(item)
  }
  return groups
}

// Order groups so most-impactful first
const TYPE_ORDER = ['screenshot', 'duplicate', 'near_duplicate', 'large_file', 'old_file']

function sortedGroupKeys(groups: Record<string, FileSuggestion[]>): string[] {
  const keys = Object.keys(groups)
  return [
    ...TYPE_ORDER.filter(k => keys.includes(k)),
    ...keys.filter(k => !TYPE_ORDER.includes(k)),
  ]
}

// ─── FileGroup sub-component ─────────────────────────────────────────────────

type GroupProps = {
  type: string
  items: FileSuggestion[]
  selectedIds: Set<string>
  onSelect: (id: string, checked: boolean) => void
  onSelectAll: (type: string, checked: boolean) => void
  onConfirmGroup: (items: FileSuggestion[]) => void
  onSkipGroup: (type: string) => void
  onProtectGroup: (items: FileSuggestion[]) => void
  onConfirmOne: (s: FileSuggestion) => void
  onSkipOne: (id: string) => void
  onProtectOne: (s: FileSuggestion) => void
}

function FileGroup({
  type, items, selectedIds,
  onSelect, onSelectAll, onConfirmGroup, onSkipGroup, onProtectGroup,
  onConfirmOne, onSkipOne, onProtectOne,
}: GroupProps) {
  const [open, setOpen] = useState(true)

  const color = TYPE_COLORS[type] ?? '#8A8A96'
  const label = TYPE_LABELS[type] ?? type
  const Icon = getGroupIcon(type)
  const totalBytes = items.reduce((s, x) => s + x.size_bytes, 0)
  const selectedInGroup = items.filter(x => selectedIds.has(x.id))
  const allSelected = selectedInGroup.length === items.length
  const someSelected = selectedInGroup.length > 0 && !allSelected

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: `1px solid #2A2A2E`, background: '#161618' }}
    >
      {/* ── Group header ── */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        style={{ borderBottom: open ? '1px solid #2A2A2E' : 'none' }}
        onClick={() => setOpen(v => !v)}
      >
        {/* Collapse icon */}
        <span style={{ color: '#5A5A66' }}>
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        </span>

        {/* Type badge */}
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded"
          style={{ background: color + '18', border: `1px solid ${color}33` }}
        >
          <Icon size={13} style={{ color }} />
          <span className="text-xs font-mono" style={{ color }}>{label}</span>
        </div>

        {/* File count + size */}
        <span className="text-xs font-mono" style={{ color: '#8A8A96' }}>
          {items.length} file{items.length !== 1 ? 's' : ''} · {fmt(totalBytes)}
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Group-level action buttons — stop propagation so header click doesn't toggle */}
        <div
          className="flex items-center gap-1.5"
          onClick={e => e.stopPropagation()}
        >
          {/* Select All checkbox */}
          <label
            className="flex items-center gap-1.5 text-xs font-mono cursor-pointer px-2 py-1 rounded"
            style={{ color: '#8A8A96', background: '#2A2A2E' }}
            onClick={e => e.stopPropagation()}
          >
            <input
              type="checkbox"
              checked={allSelected}
              ref={el => { if (el) el.indeterminate = someSelected }}
              onChange={e => onSelectAll(type, e.target.checked)}
              style={{ accentColor: '#7B61FF', width: 13, height: 13, cursor: 'pointer' }}
            />
            Select all
          </label>

          {/* Delete selected or group */}
          <button
            onClick={() => onConfirmGroup(someSelected || allSelected ? selectedInGroup : items)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono"
            style={{ background: '#FF4D4D18', color: '#FF4D4D', border: '1px solid #FF4D4D33' }}
            title={someSelected || allSelected ? 'Delete selected in group' : 'Delete entire group'}
          >
            <Trash2 size={12} />
            {someSelected || allSelected ? `Delete ${selectedInGroup.length}` : 'Delete group'}
          </button>

          {/* Skip group */}
          <button
            onClick={() => onSkipGroup(type)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono"
            style={{ background: '#2A2A2E', color: '#8A8A96' }}
          >
            <SkipForward size={12} />
            Skip
          </button>

          {/* Protect group */}
          <button
            onClick={() => onProtectGroup(items)}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs font-mono"
            style={{ background: '#7B61FF18', color: '#7B61FF', border: '1px solid #7B61FF33' }}
          >
            <ShieldCheck size={12} />
            Protect
          </button>
        </div>
      </div>

      {/* ── File list ── */}
      {open && (
        <div className="divide-y divide-[#1E1E20]">
          {items.map(s => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              selected={selectedIds.has(s.id)}
              onSelect={onSelect}
              onConfirm={onConfirmOne}
              onSkip={onSkipOne}
              onProtect={onProtectOne}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── StoragePage ──────────────────────────────────────────────────────────────

export function StoragePage() {
  // Use the scan store so the page talks to the same live API contract as the backend.
  const {
    status,
    progress,
    startScan,
    error,
    suggestions,
    selectedIds,
    setSuggestions,
    setSelectedIds,
<<<<<<< HEAD
=======
  const {
    status, progress, startScan, error,
    suggestions, selectedIds, setSuggestions, setSelectedIds
>>>>>>> 1af2d7dc88e62cb71f5293a9f6ee6307b761607d
  } = useScanStore()
  const [modalItems, setModalItems] = useState<FileSuggestion[]>([])
  const { confirm, skip } = useConsent(setSuggestions)

  // ── Native directory picker ──
  const pickDir = async () => {
    const dir = window.electron?.openDirectory
      ? await window.electron.openDirectory()
      : prompt('Enter directory path:')
    if (dir) {
      // store.startScan already clears suggestions + selectedIds
      startScan(dir)
    }
  }

  // ── Groups ──
  const groups = useMemo(() => groupSuggestions(suggestions), [suggestions])
  const groupKeys = useMemo(() => sortedGroupKeys(groups), [groups])

  const totalBytes = suggestions.reduce((s, x) => s + x.size_bytes, 0)
  const selectedList = suggestions.filter(x => selectedIds.has(x.id))

  // ── Selection handlers ──
  const handleSelect = (id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const handleSelectAll = (type: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      for (const s of (groups[type] ?? [])) {
        if (checked) next.add(s.id)
        else next.delete(s.id)
      }
      return next
    })
  }

  const handleSelectAllGroups = () => {
    setSelectedIds(new Set(suggestions.map(s => s.id)))
  }

  const handleDeselectAll = () => setSelectedIds(new Set())

  // ── Confirm (delete) handlers ──
  const handleConfirmBatch = async (items: FileSuggestion[]) => {
    setModalItems([])
    for (const s of items) await confirm(s)
    setSelectedIds(prev => {
      const next = new Set(prev)
      for (const s of items) next.delete(s.id)
      return next
    })
  }

  const handleConfirmOne = (s: FileSuggestion) => {
    setModalItems([s])
  }

  const handleConfirmGroup = (items: FileSuggestion[]) => {
    setModalItems(items)
  }

  const handleDeleteAll = () => {
    setModalItems(suggestions)
  }

  const handleDeleteSelected = () => {
    if (selectedList.length > 0) setModalItems(selectedList)
  }

  // ── Skip handlers ──
  const handleSkipOne = (id: string) => {
    skip(id)
    setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n })
  }

  const handleSkipGroup = (type: string) => {
    for (const s of (groups[type] ?? [])) skip(s.id)
    setSelectedIds(prev => {
      const next = new Set(prev)
      for (const s of (groups[type] ?? [])) next.delete(s.id)
      return next
    })
  }

  // ── Protect handlers ──
  const handleProtectOne = async (s: FileSuggestion) => {
    const name = s.path.replace(/\\/g, '/').split('/').pop() ?? s.path
    await api.addProtectedRule('path', s.path, name)
    setSuggestions(prev => prev.filter(x => x.id !== s.id))
    setSelectedIds(prev => { const n = new Set(prev); n.delete(s.id); return n })
  }

  const handleProtectGroup = async (items: FileSuggestion[]) => {
    for (const s of items) {
      const name = s.path.replace(/\\/g, '/').split('/').pop() ?? s.path
      await api.addProtectedRule('path', s.path, name)
    }
    const ids = new Set(items.map(x => x.id))
    setSuggestions(prev => prev.filter(x => !ids.has(x.id)))
    setSelectedIds(prev => {
      const next = new Set(prev)
      for (const id of ids) next.delete(id)
      return next
    })
  }

  const isScanning = status === 'scanning' || status === 'generating_reasons'
  const allSelected = suggestions.length > 0 && selectedIds.size === suggestions.length

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-2xl" style={{ color: '#F2F2F3' }}>Storage Scanner</h1>
          {suggestions.length > 0 && (
            <p className="text-xs font-mono mt-0.5" style={{ color: '#8A8A96' }}>
              {suggestions.length} items · {fmt(totalBytes)} reclaimable
            </p>
          )}
        </div>

        <button
          onClick={pickDir}
          disabled={isScanning}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono disabled:opacity-50 transition-opacity"
          style={{ background: '#7B61FF', color: '#fff' }}
        >
          <FolderOpen size={15} />
          Choose Directory
        </button>
      </div>

      {/* ── Progress ── */}
      {isScanning && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-mono" style={{ color: '#8A8A96' }}>
            <Loader2 size={14} className="animate-spin" />
            {status === 'scanning' ? 'Scanning files…' : 'Generating AI reasons…'}
          </div>
          <div className="h-1 rounded-full overflow-hidden" style={{ background: '#2A2A2E' }}>
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

      {/* ── Bulk action toolbar ── */}
      {suggestions.length > 0 && !isScanning && (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{ background: '#161618', border: '1px solid #2A2A2E' }}
        >
          {/* Select all groups checkbox */}
          <label className="flex items-center gap-2 text-xs font-mono cursor-pointer" style={{ color: '#8A8A96' }}>
            <input
              type="checkbox"
              checked={allSelected}
              ref={el => { if (el) el.indeterminate = selectedIds.size > 0 && !allSelected }}
              onChange={e => e.target.checked ? handleSelectAllGroups() : handleDeselectAll()}
              style={{ accentColor: '#7B61FF', width: 14, height: 14, cursor: 'pointer' }}
            />
            {allSelected ? 'Deselect all' : 'Select all'}
          </label>

          <div style={{ width: 1, height: 20, background: '#2A2A2E' }} />

          {/* Delete selected */}
          {selectedList.length > 0 && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono"
              style={{ background: '#FF4D4D18', color: '#FF4D4D', border: '1px solid #FF4D4D33' }}
            >
              <Trash2 size={12} />
              Delete selected ({selectedList.length})
            </button>
          )}

          {/* Delete ALL groups */}
          <button
            onClick={handleDeleteAll}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono"
            style={{ background: '#FF4D4D', color: '#fff' }}
          >
            <Trash2 size={12} />
            Delete all {suggestions.length} files
          </button>

          <div className="flex-1" />

          {/* Skip all */}
          <button
            onClick={() => { setSuggestions([]); setSelectedIds(new Set<string>()) }}
            className="text-xs font-mono px-3 py-1.5 rounded-lg"
            style={{ background: '#2A2A2E', color: '#8A8A96' }}
          >
            Skip all
          </button>
        </div>
      )}

      {/* ── Grouped suggestion cards ── */}
      {groupKeys.length > 0 && (
        <div className="space-y-4">
          {groupKeys.map(type => (
            <FileGroup
              key={type}
              type={type}
              items={groups[type]}
              selectedIds={selectedIds}
              onSelect={handleSelect}
              onSelectAll={handleSelectAll}
              onConfirmGroup={handleConfirmGroup}
              onSkipGroup={handleSkipGroup}
              onProtectGroup={handleProtectGroup}
              onConfirmOne={handleConfirmOne}
              onSkipOne={handleSkipOne}
              onProtectOne={handleProtectOne}
            />
          ))}
        </div>
      )}

      {/* ── Empty state ── */}
      {status === 'complete' && suggestions.length === 0 && (
        <div
          className="rounded-xl p-8 text-center"
          style={{ background: '#161618', border: '1px solid #2A2A2E' }}
        >
          <p className="font-mono text-sm" style={{ color: '#22C55E' }}>
            No clutter found — or all items cleared.
          </p>
          <p className="font-mono text-xs mt-1" style={{ color: '#5A5A66' }}>
            Choose another directory to scan.
          </p>
        </div>
      )}

      {/* ── Consent modal (single or batch) ── */}
      <ConsentModal
        suggestions={modalItems}
        open={modalItems.length > 0}
        onConfirm={handleConfirmBatch}
        onCancel={() => setModalItems([])}
      />
    </div>
  )
}
