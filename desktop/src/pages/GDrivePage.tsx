import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Cloud, Search, Copy, FolderTree, Archive, Trash2, Check, Star,
  ChevronRight, ChevronUp, ChevronDown, Loader2, ShieldCheck, AlertTriangle,
  RotateCcw, FileText, Image as ImageIcon, Video, Music, Code, File as FileIcon,
  Sparkles, Clock, Tags, MapPin, HardDrive,
} from 'lucide-react'
import { api } from '../lib/api'
import type {
  DriveScanStatus, DriveCluster, DriveDeletionList, DriveDeletionBucket, DriveOrganisePlan,
  DriveCompression, DriveExecuteReport, DriveFile,
} from '../lib/api'

// ── palette (matches App shell) ────────────────────────────────────────────
const C = {
  bg: '#0D0D0F', card: '#161618', card2: '#1C1C20', border: '#2A2A2E',
  accent: '#7B61FF', accentSoft: '#7B61FF22', muted: '#8A8A96', text: '#E7E7EA',
  green: '#3FB950', red: '#F85149', amber: '#D29922',
}

const fmt = (b: number) => {
  if (b >= 1e9) return `${(b / 1e9).toFixed(1)} GB`
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB`
  return `${b} B`
}

const STEPS = [
  { n: 1, label: 'Scan',     icon: Search },
  { n: 2, label: 'Review',   icon: Copy },
  { n: 3, label: 'Organize', icon: Tags },
  { n: 4, label: 'Compress', icon: Archive },
  { n: 5, label: 'Folders',  icon: FolderTree },
  { n: 6, label: 'Clean up', icon: Trash2 },
] as const

const PARADIGMS = [
  { key: 'type',     label: 'By File Type',       desc: 'Images / Docs / Videos / Code', icon: FileText },
  { key: 'category', label: 'By Content Category', desc: 'Personal / Work / Downloads',   icon: Tags },
  { key: 'time',     label: 'By Time Pattern',     desc: 'Recent / Active / Archive',     icon: Clock },
  { key: 'location', label: 'By Location',         desc: 'Geotagged media',               icon: MapPin },
  { key: 'smart',    label: 'Smart Groups',        desc: 'AI-suggested folders',          icon: Sparkles },
] as const

function mimeIcon(mime: string, size = 18) {
  const p = { size, color: C.muted }
  if (mime.startsWith('image/')) return <ImageIcon {...p} />
  if (mime.startsWith('video/')) return <Video {...p} />
  if (mime.startsWith('audio/')) return <Music {...p} />
  if (mime.includes('pdf') || mime.includes('document') || mime.includes('text')) return <FileText {...p} />
  if (mime.includes('script') || mime.includes('json')) return <Code {...p} />
  return <FileIcon {...p} />
}

export default function GDrivePage() {
  const [step, setStep] = useState(1)
  const [linked, setLinked] = useState(false)
  const [email, setEmail] = useState<string | null>(null)
  const [banner, setBanner] = useState('')

  const [scanId, setScanId] = useState<string | null>(null)
  const [scan, setScan] = useState<DriveScanStatus | null>(null)
  const [clusters, setClusters] = useState<DriveCluster[]>([])
  const [paradigms, setParadigms] = useState<string[]>(['type', 'time'])
  const [plan, setPlan] = useState<DriveOrganisePlan | null>(null)
  const [compression, setCompression] = useState<DriveCompression | null>(null)
  const [deletion, setDeletion] = useState<DriveDeletionList | null>(null)
  const [report, setReport] = useState<DriveExecuteReport | null>(null)

  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [doCompress, setDoCompress] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    api.getDriveAuthStatus().then(d => { setLinked(d.linked); setEmail(d.email) })
    const params = new URLSearchParams(window.location.search)
    if (params.get('linked') === '1') {
      setBanner('Google Drive linked successfully.')
      window.history.replaceState({}, '', '/gdrive')
      api.getDriveAuthStatus().then(d => { setLinked(d.linked); setEmail(d.email) })
    } else if (params.get('error')) {
      setBanner(`Link failed: ${params.get('error')}`)
      window.history.replaceState({}, '', '/gdrive')
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const linkAccount = () => {
    api.getDriveAuthUrl().then(d => {
      const opener = (window as any).electron?.openExternal
      if (opener) opener(d.auth_url)
      else window.open(d.auth_url, '_blank')
    })
  }

  const startScan = async () => {
    setBusy(true); setBanner('')
    try {
      const { scan_id } = await api.startDriveScan()
      setScanId(scan_id)
      setScan({ scan_id, status: 'pending', phase: 'Starting', progress: 0 } as DriveScanStatus)
      pollRef.current = setInterval(async () => {
        const s = await api.getDriveScanStatus(scan_id)
        setScan(s)
        if (s.status === 'done' || s.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          if (s.status === 'done') {
            const c = await api.getDriveClusters(scan_id)
            setClusters(c.clusters)
          }
        }
      }, 1200)
    } finally { setBusy(false) }
  }

  const reloadClusters = useCallback(async () => {
    if (scanId) setClusters((await api.getDriveClusters(scanId)).clusters)
  }, [scanId])

  const keepFile = async (f: DriveFile, description: string, flag: string) => {
    if (!scanId) return
    await api.keepDriveFile(scanId, { record_id: f.id, description, flag })
    await reloadClusters()
  }

  const goToOrganizePreview = async () => {
    if (!scanId) return
    setBusy(true)
    try {
      const [p, comp] = await Promise.all([
        api.organiseDrive(scanId, paradigms),
        api.getDriveCompression(scanId),
      ])
      setPlan(p); setCompression(comp)
      setStep(4)
    } finally { setBusy(false) }
  }

  const goToDeletion = async () => {
    if (!scanId) return
    setBusy(true)
    try { setDeletion(await api.getDriveDeletionList(scanId)); setStep(6) }
    finally { setBusy(false) }
  }

  const toggleDeletion = async (record_id: number, include: boolean) => {
    if (!scanId) return
    await api.toggleDriveDeletion(scanId, record_id, include)
    setDeletion(await api.getDriveDeletionList(scanId))
  }

  const execute = async () => {
    if (!scanId) return
    setConfirm(false); setBusy(true)
    try {
      const r = await api.executeDriveCleanup(scanId, {
        do_delete: true, do_organize: true, do_compress: doCompress,
      })
      setReport(r)
    } finally { setBusy(false) }
  }

  const undo = async () => {
    if (!scanId) return
    setBusy(true)
    try {
      const r = await api.undoDriveCleanup(scanId)
      setBanner(`Undo complete — restored ${r.restored} files, moved back ${r.moved_back}.`)
      setReport(null)
    } finally { setBusy(false) }
  }

  const scanDone = scan?.status === 'done'

  return (
    <div style={{ background: C.bg, minHeight: '100%', color: C.text }}>
      <div className="max-w-4xl mx-auto p-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: C.accentSoft }}>
              <Cloud size={22} color={C.accent} />
            </div>
            <div>
              <h1 className="text-xl font-semibold" style={{ color: C.text }}>Cloud Cleanup &amp; Organization</h1>
              <p className="text-sm" style={{ color: C.muted }}>Privacy-first Google Drive declutter — metadata only, never file contents.</p>
            </div>
          </div>
          {email && (
            <span className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full"
              style={{ background: '#12331F', color: C.green, border: `1px solid ${C.green}55` }}>
              <Check size={13} /> {email}
            </span>
          )}
        </div>

        {/* Stepper */}
        <Stepper current={step} unlocked={scanDone} onJump={setStep} />

        {banner && (
          <div className="rounded-lg px-4 py-3 text-sm flex items-center gap-2"
            style={{ background: C.accentSoft, color: C.text, border: `1px solid ${C.accent}55` }}>
            <ShieldCheck size={16} color={C.accent} /> {banner}
          </div>
        )}

        {/* ── STEP 1 ── */}
        {step === 1 && (
          <Card>
            {!linked ? (
              <div className="text-center py-8 space-y-4">
                <p style={{ color: C.muted }}>Connect your Google Drive to begin a privacy-first cleanup.</p>
                <Button onClick={linkAccount}><Cloud size={16} /> Link Google Drive</Button>
              </div>
            ) : (
              <div className="space-y-5">
                <Row title="Scan your Drive" sub="Reads only names, sizes, dates and checksums. Duplicates are grouped, nothing is deleted yet.">
                  <Button onClick={startScan} disabled={busy || scan?.status === 'scanning'}>
                    {scan?.status === 'scanning'
                      ? <><Loader2 size={16} className="animate-spin" /> Scanning…</>
                      : <><Search size={16} /> Start scan</>}
                  </Button>
                </Row>

                {scan && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs" style={{ color: C.muted }}>
                      <span>{scan.phase ?? scan.status} — {scan.processed_files}/{scan.total_files || '?'} files</span>
                      <span>{scan.progress}%</span>
                    </div>
                    <Progress value={scan.progress} />
                    {scanDone && (
                      <div className="grid grid-cols-3 gap-3 pt-2">
                        <Stat label="Files scanned" value={scan.total_files} />
                        <Stat label="Duplicate clusters" value={scan.clusters_found} accent={C.amber} />
                        <Stat label="Reclaimable" value={fmt(scan.bytes_reclaimable)} accent={C.green} />
                      </div>
                    )}
                    {scan.status === 'error' && (
                      <p className="text-sm" style={{ color: C.red }}>{scan.error_message}</p>
                    )}
                  </div>
                )}

                {scanDone && (
                  <NextButton onClick={() => setStep(2)}>Review duplicates</NextButton>
                )}
              </div>
            )}
          </Card>
        )}

        {/* ── STEP 2 ── */}
        {step === 2 && (
          <div className="space-y-4">
            <Card>
              <Row title="Review duplicate clusters"
                sub="Pick one file to keep per cluster. Add a private description to protect similar files in future. The rest move to the deletion list.">
                <NextButton onClick={() => setStep(3)}>Choose organization</NextButton>
              </Row>
            </Card>
            {clusters.length === 0
              ? <Empty icon={Copy} text="No duplicate clusters found. You can move straight to organizing." />
              : clusters.map(c => (
                  <ClusterCard key={c.group_id} cluster={c} onKeep={keepFile} />
                ))}
          </div>
        )}

        {/* ── STEP 3 ── */}
        {step === 3 && (
          <Card>
            <Row title="How should I organize your Drive?"
              sub="Select the paradigms to apply. Drag priority with the arrows — the top one is primary." />
            <ParadigmPicker selected={paradigms} onChange={setParadigms} />
            <NextButton onClick={goToOrganizePreview} disabled={busy || paradigms.length === 0}>
              {busy ? <><Loader2 size={16} className="animate-spin" /> Building plan…</> : 'Preview compression'}
            </NextButton>
          </Card>
        )}

        {/* ── STEP 4 ── */}
        {step === 4 && (
          <Card>
            <Row title="Compression preview"
              sub="Large, uncompressed files that aren't slated for deletion. Encoding runs in the background after cleanup." />
            {!compression || compression.count === 0 ? (
              <Empty icon={Archive} text="No compression candidates over 100 MB." />
            ) : (
              <>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <Stat label="Candidates" value={compression.count} />
                  <Stat label="Current size" value={fmt(compression.original_bytes)} />
                  <Stat label="Est. savings" value={fmt(compression.savings_bytes)} accent={C.green} />
                </div>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {compression.candidates.map(c => (
                    <div key={c.record_id} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm"
                      style={{ background: C.card2 }}>
                      <span className="truncate max-w-xs" style={{ color: C.text }}>{c.name}</span>
                      <span style={{ color: C.muted }}>
                        {fmt(c.original_size)} → {fmt(c.estimated_size)}
                        <span style={{ color: C.green }} className="ml-2">-{c.savings_pct}%</span>
                      </span>
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-2 mt-4 text-sm cursor-pointer" style={{ color: C.muted }}>
                  <input type="checkbox" checked={doCompress} onChange={e => setDoCompress(e.target.checked)}
                    style={{ accentColor: C.accent }} />
                  Queue these files for compression during cleanup
                </label>
              </>
            )}
            <NextButton onClick={() => setStep(5)}>Preview folder structure</NextButton>
          </Card>
        )}

        {/* ── STEP 5 ── */}
        {step === 5 && (
          <Card>
            <Row title="New folder structure"
              sub={`${plan?.files_planned ?? 0} files will be organized into these folders on Google Drive.`} />
            {!plan || plan.folders.length === 0
              ? <Empty icon={FolderTree} text="No folders planned." />
              : <FolderPreview folders={plan.folders} />}
            <NextButton onClick={goToDeletion} disabled={busy}>
              {busy ? <><Loader2 size={16} className="animate-spin" /> Loading…</> : 'Review deletion list'}
            </NextButton>
          </Card>
        )}

        {/* ── STEP 6 ── */}
        {step === 6 && (
          report
            ? <ReportCard report={report} onUndo={undo} busy={busy} />
            : <DeletionReview deletion={deletion} plan={plan} compression={doCompress ? compression : null}
                onToggle={toggleDeletion} onExecute={() => setConfirm(true)} busy={busy} />
        )}
      </div>

      {confirm && deletion && (
        <ConfirmModal deletion={deletion} plan={plan} compress={doCompress}
          onCancel={() => setConfirm(false)} onConfirm={execute} />
      )}
    </div>
  )
}

// ── Layout primitives ───────────────────────────────────────────────────────
function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl p-5 space-y-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
      {children}
    </div>
  )
}

function Row({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h2 className="font-medium" style={{ color: C.text }}>{title}</h2>
        {sub && <p className="text-sm mt-1 leading-relaxed" style={{ color: C.muted }}>{sub}</p>}
      </div>
      {children && <div className="shrink-0">{children}</div>}
    </div>
  )
}

function Button({ children, onClick, disabled, variant = 'primary' }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; variant?: 'primary' | 'danger' | 'ghost'
}) {
  const bg = variant === 'danger' ? C.red : variant === 'ghost' ? C.card2 : C.accent
  const color = variant === 'ghost' ? C.text : '#fff'
  return (
    <button onClick={onClick} disabled={disabled}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-40 disabled:cursor-not-allowed"
      style={{ background: bg, color }}>
      {children}
    </button>
  )
}

function NextButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition disabled:opacity-40 disabled:cursor-not-allowed mt-2"
      style={{ background: C.accentSoft, color: C.accent, border: `1px solid ${C.accent}55` }}>
      {children} <ChevronRight size={16} />
    </button>
  )
}

function Progress({ value }: { value: number }) {
  return (
    <div className="w-full rounded-full h-2 overflow-hidden" style={{ background: C.card2 }}>
      <div className="h-2 rounded-full transition-all" style={{ width: `${value}%`, background: C.accent }} />
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div className="rounded-lg p-3 text-center" style={{ background: C.card2 }}>
      <p className="text-lg font-semibold" style={{ color: accent ?? C.text }}>{value}</p>
      <p className="text-xs mt-0.5" style={{ color: C.muted, fontFamily: 'DM Mono, monospace' }}>{label}</p>
    </div>
  )
}

function Empty({ icon: Icon, text }: { icon: any; text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center">
      <Icon size={28} color={C.muted} />
      <p className="text-sm" style={{ color: C.muted }}>{text}</p>
    </div>
  )
}

function Stepper({ current, unlocked, onJump }: { current: number; unlocked: boolean; onJump: (n: number) => void }) {
  return (
    <div className="flex items-center">
      {STEPS.map((s, i) => {
        const active = current === s.n
        const done = current > s.n
        const clickable = unlocked || s.n === 1
        const Icon = s.icon
        return (
          <div key={s.n} className="flex items-center flex-1 last:flex-none">
            <button onClick={() => clickable && onJump(s.n)} disabled={!clickable}
              className="flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm font-medium transition disabled:cursor-not-allowed"
              style={{
                color: active ? C.accent : done ? C.green : C.muted,
                background: active ? C.accentSoft : 'transparent',
              }}>
              <span className="w-6 h-6 rounded-full flex items-center justify-center shrink-0"
                style={{
                  background: active ? C.accent : done ? C.green : C.card2,
                  color: active || done ? '#fff' : C.muted,
                }}>
                {done ? <Check size={13} /> : <Icon size={13} />}
              </span>
              <span className="hidden md:inline">{s.label}</span>
            </button>
            {i < STEPS.length - 1 && <div className="flex-1 h-px mx-1" style={{ background: C.border }} />}
          </div>
        )
      })}
    </div>
  )
}

// ── Step 2: cluster card ─────────────────────────────────────────────────────
function ClusterCard({ cluster, onKeep }: { cluster: DriveCluster; onKeep: (f: DriveFile, desc: string, flag: string) => void }) {
  const [selected, setSelected] = useState<number | null>(
    cluster.files.find(f => f.is_cluster_original)?.id ?? cluster.files[0]?.id ?? null,
  )
  const [desc, setDesc] = useState('')
  const [flag, setFlag] = useState('normal')
  const [saved, setSaved] = useState(cluster.files.some(f => f.is_protected))

  const selectedFile = cluster.files.find(f => f.id === selected)

  return (
    <div className="rounded-xl p-4 space-y-3" style={{ background: C.card, border: `1px solid ${saved ? C.green + '66' : C.border}` }}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: C.text }}>
          {cluster.count} identical copies · {fmt(cluster.total_bytes)}
        </span>
        {saved && <span className="flex items-center gap-1 text-xs" style={{ color: C.green }}><ShieldCheck size={13} /> Protected</span>}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {cluster.files.slice(0, 6).map(f => {
          const isSel = f.id === selected
          return (
            <button key={f.id} onClick={() => setSelected(f.id)}
              className="rounded-lg p-2 text-left transition"
              style={{ background: C.card2, border: `1px solid ${isSel ? C.accent : 'transparent'}` }}>
              <div className="flex items-center gap-2">
                {f.thumbnail_link
                  ? <img src={f.thumbnail_link} alt="" referrerPolicy="no-referrer"
                      className="w-8 h-8 rounded object-cover" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                  : mimeIcon(f.mime_type)}
                {isSel && <Star size={13} color={C.accent} fill={C.accent} />}
              </div>
              <p className="text-xs mt-1.5 truncate" style={{ color: C.text }}>{f.name}</p>
              <p className="text-xs" style={{ color: C.muted }}>{fmt(f.size_bytes)}</p>
            </button>
          )
        })}
      </div>

      {selectedFile && (
        <div className="space-y-2 pt-1">
          <input value={desc} onChange={e => setDesc(e.target.value)}
            placeholder={`Describe "${selectedFile.name}" (stored locally only)`}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.text }} />
          <div className="flex items-center gap-2">
            <select value={flag} onChange={e => setFlag(e.target.value)}
              className="rounded-lg px-2 py-2 text-sm outline-none"
              style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.text }}>
              <option value="normal">Normal</option>
              <option value="review_later">Review later</option>
              <option value="keep_forever">Keep forever</option>
            </select>
            <button onClick={() => { onKeep(selectedFile, desc, flag); setSaved(true) }}
              className="flex-1 inline-flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition"
              style={{ background: C.accent, color: '#fff' }}>
              <Star size={14} /> Keep this &amp; list the rest
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Step 3: paradigm picker with priority ────────────────────────────────────
function ParadigmPicker({ selected, onChange }: { selected: string[]; onChange: (v: string[]) => void }) {
  const toggle = (key: string) =>
    onChange(selected.includes(key) ? selected.filter(k => k !== key) : [...selected, key])
  const move = (idx: number, dir: -1 | 1) => {
    const next = [...selected]
    const j = idx + dir
    if (j < 0 || j >= next.length) return
    ;[next[idx], next[j]] = [next[j], next[idx]]
    onChange(next)
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {PARADIGMS.map(p => {
          const on = selected.includes(p.key)
          const Icon = p.icon
          return (
            <button key={p.key} onClick={() => toggle(p.key)}
              className="flex items-start gap-3 p-3 rounded-lg text-left transition"
              style={{ background: C.card2, border: `1px solid ${on ? C.accent : C.border}` }}>
              <Icon size={18} color={on ? C.accent : C.muted} className="mt-0.5" />
              <div>
                <p className="text-sm font-medium" style={{ color: C.text }}>{p.label}</p>
                <p className="text-xs" style={{ color: C.muted }}>{p.desc}</p>
              </div>
              {on && <Check size={16} color={C.accent} className="ml-auto" />}
            </button>
          )
        })}
      </div>

      {selected.length > 0 && (
        <div className="rounded-lg p-3" style={{ background: C.card2 }}>
          <p className="text-xs mb-2" style={{ color: C.muted, fontFamily: 'DM Mono, monospace' }}>PRIORITY ORDER</p>
          <div className="space-y-1.5">
            {selected.map((key, idx) => {
              const p = PARADIGMS.find(x => x.key === key)!
              return (
                <div key={key} className="flex items-center gap-2 rounded-md px-2 py-1.5" style={{ background: C.card }}>
                  <span className="text-xs w-5 text-center" style={{ color: C.accent }}>{idx + 1}</span>
                  <span className="text-sm flex-1" style={{ color: C.text }}>{p.label}</span>
                  <button onClick={() => move(idx, -1)} disabled={idx === 0} className="disabled:opacity-30">
                    <ChevronUp size={16} color={C.muted} />
                  </button>
                  <button onClick={() => move(idx, 1)} disabled={idx === selected.length - 1} className="disabled:opacity-30">
                    <ChevronDown size={16} color={C.muted} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Step 5: folder preview ────────────────────────────────────────────────────
function FolderPreview({ folders }: { folders: { path: string; count: number }[] }) {
  return (
    <div className="rounded-lg p-4 max-h-80 overflow-y-auto" style={{ background: C.card2, fontFamily: 'DM Mono, monospace' }}>
      {folders.map(f => (
        <div key={f.path} className="flex items-center justify-between py-1 text-sm">
          <span className="flex items-center gap-2" style={{ color: C.text }}>
            <FolderTree size={14} color={C.accent} />
            {f.path.split('/').map((seg, i) => (
              <span key={i} style={{ color: i === 0 ? C.muted : C.text }}>
                {i > 0 && <span style={{ color: C.muted }}> / </span>}{seg}
              </span>
            ))}
          </span>
          <span style={{ color: C.muted }}>{f.count}</span>
        </div>
      ))}
    </div>
  )
}

// ── Step 6: deletion review ───────────────────────────────────────────────────
function DeletionReview({ deletion, plan, compression, onToggle, onExecute, busy }: {
  deletion: DriveDeletionList | null
  plan: DriveOrganisePlan | null
  compression: DriveCompression | null
  onToggle: (record_id: number, include: boolean) => void
  onExecute: () => void
  busy: boolean
}) {
  if (!deletion) return <Card><Empty icon={Loader2} text="Loading deletion list…" /></Card>
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#3B1F1F' }}>
            <Trash2 size={20} color={C.red} />
          </div>
          <div>
            <h2 className="font-medium" style={{ color: C.text }}>Ready to clean up</h2>
            <p className="text-sm" style={{ color: C.muted }}>
              {deletion.total_files} files · {fmt(deletion.total_bytes)} · {deletion.avg_confidence}% avg confidence safe to delete
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 pt-1">
          <Stat label="With descriptions" value={deletion.excluded.described} accent={C.green} />
          <Stat label="Protected" value={deletion.excluded.protected} accent={C.green} />
          <Stat label="Kept / recent" value={deletion.excluded.recent} accent={C.green} />
        </div>
        <p className="text-xs flex items-center gap-1.5" style={{ color: C.muted }}>
          <ShieldCheck size={13} color={C.green} /> Excluded items above are never deleted.
        </p>
      </Card>

      {deletion.buckets.map(b => <DeletionBucket key={b.key} bucket={b} onToggle={onToggle} />)}

      <Card>
        <Row title="Summary of changes"
          sub={`Delete ${deletion.total_files} files · Organize ${plan?.files_planned ?? 0} files into ${plan?.folders.length ?? 0} folders${compression ? ` · Compress ${compression.count} files` : ''}.`} />
        <Button variant="danger" onClick={onExecute} disabled={busy || deletion.total_files === 0}>
          {busy ? <><Loader2 size={16} className="animate-spin" /> Working…</> : <><Trash2 size={16} /> Delete &amp; organize</>}
        </Button>
      </Card>
    </div>
  )
}

function DeletionBucket({ bucket, onToggle }: { bucket: DriveDeletionBucket; onToggle: (id: number, include: boolean) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-xl overflow-hidden" style={{ background: C.card, border: `1px solid ${C.border}` }}>
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-3">
        <span className="flex items-center gap-2 text-sm font-medium" style={{ color: C.text }}>
          {open ? <ChevronDown size={16} color={C.muted} /> : <ChevronRight size={16} color={C.muted} />}
          {bucket.label}
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: C.card2, color: C.muted }}>
            {bucket.count} · {fmt(bucket.total_bytes)}
          </span>
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-1 max-h-64 overflow-y-auto">
          {bucket.files.slice(0, 50).map((f: DriveFile) => (
            <div key={f.id} className="flex items-center gap-2 rounded-md px-2 py-1.5" style={{ background: C.card2 }}>
              {mimeIcon(f.mime_type, 15)}
              <span className="text-sm truncate flex-1" style={{ color: C.text }}>{f.name}</span>
              <span className="text-xs" style={{ color: C.muted }}>{fmt(f.size_bytes)}</span>
              <button onClick={() => onToggle(f.id, false)} title="Keep this file"
                className="text-xs px-2 py-0.5 rounded transition"
                style={{ background: C.card, color: C.green, border: `1px solid ${C.green}55` }}>
                Keep
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ReportCard({ report, onUndo, busy }: { report: DriveExecuteReport; onUndo: () => void; busy: boolean }) {
  return (
    <Card>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#12331F' }}>
          <Check size={20} color={C.green} />
        </div>
        <h2 className="font-medium" style={{ color: C.text }}>Cleanup complete</h2>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat label="Deleted" value={report.deleted} accent={C.red} />
        <Stat label="Organized" value={report.moved} accent={C.accent} />
        <Stat label="Folders" value={report.folders_created} />
        <Stat label="Protected" value={report.protected} accent={C.green} />
      </div>
      <p className="text-xs" style={{ color: C.muted }}>
        Deleted files sit in Google Drive Trash and can be restored for 30 days.
      </p>
      <Button variant="ghost" onClick={onUndo} disabled={busy}>
        {busy ? <><Loader2 size={16} className="animate-spin" /> Undoing…</> : <><RotateCcw size={16} /> Undo last cleanup</>}
      </Button>
    </Card>
  )
}

function ConfirmModal({ deletion, plan, compress, onCancel, onConfirm }: {
  deletion: DriveDeletionList; plan: DriveOrganisePlan | null; compress: boolean
  onCancel: () => void; onConfirm: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: '#000000AA' }}>
      <div className="rounded-2xl p-6 max-w-md w-full space-y-4" style={{ background: C.card, border: `1px solid ${C.border}` }}>
        <div className="flex items-center gap-2">
          <AlertTriangle size={20} color={C.amber} />
          <h3 className="font-semibold" style={{ color: C.text }}>Are you sure?</h3>
        </div>
        <ul className="text-sm space-y-1.5" style={{ color: C.muted }}>
          <li className="flex items-center gap-2"><Trash2 size={14} color={C.red} /> Delete {deletion.total_files} files ({fmt(deletion.total_bytes)})</li>
          <li className="flex items-center gap-2"><FolderTree size={14} color={C.accent} /> Organize into {plan?.folders.length ?? 0} folders</li>
          {compress && <li className="flex items-center gap-2"><Archive size={14} color={C.accent} /> Queue large files for compression</li>}
          <li className="flex items-center gap-2"><ShieldCheck size={14} color={C.green} /> Protected &amp; described files untouched</li>
        </ul>
        <p className="text-xs" style={{ color: C.muted }}>
          Files go to Google Drive Trash (restorable 30 days). Local backups are unaffected.
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onCancel}>Keep everything</Button>
          <div className="flex-1" />
          <Button variant="danger" onClick={onConfirm}><Trash2 size={16} /> Confirm cleanup</Button>
        </div>
      </div>
    </div>
  )
}
