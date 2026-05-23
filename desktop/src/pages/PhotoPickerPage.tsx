import { useState, useRef } from 'react'
import { FolderOpen, Loader2, Copy } from 'lucide-react'
import { api, PhotoScore } from '../lib/api'

export function PhotoPickerPage() {
  const [status, setStatus] = useState<'idle' | 'scoring' | 'complete' | 'error'>('idle')
  const [photos, setPhotos] = useState<PhotoScore[]>([])
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const pickDir = async () => {
    const dir = window.electron?.openDirectory
      ? await window.electron.openDirectory()
      : prompt('Enter photo directory path:')
    if (!dir) return

    setPhotos([])
    setError(null)
    setStatus('scoring')

    try {
      const { job_id } = await api.startPhotoScore(dir)

      pollRef.current = setInterval(async () => {
        try {
          const { status: s } = await api.getPhotoStatus(job_id)
          if (s === 'complete') {
            clearInterval(pollRef.current!)
            const top = await api.getTopPhotos(job_id)
            setPhotos(top)
            setStatus('complete')
          } else if (s === 'error') {
            clearInterval(pollRef.current!)
            setStatus('error')
            setError('Scoring failed.')
          }
        } catch (e) {
          clearInterval(pollRef.current!)
          setStatus('error')
          setError(String(e))
        }
      }, 2000)
    } catch (e) {
      setStatus('error')
      setError(String(e))
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="font-serif text-2xl" style={{ color: '#F2F2F3' }}>Photo Picker</h1>
        <p className="font-mono text-sm mt-1" style={{ color: '#8A8A96' }}>
          Score your photos aesthetically — sharpness, brightness, composition — and pick the top 10.
        </p>
      </div>

      <button
        onClick={pickDir}
        disabled={status === 'scoring'}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-mono disabled:opacity-50"
        style={{ background: '#22C55E', color: '#0D0D0F' }}
      >
        <FolderOpen size={16} /> Choose Photo Folder
      </button>

      {status === 'scoring' && (
        <div className="flex items-center gap-2 text-sm font-mono" style={{ color: '#8A8A96' }}>
          <Loader2 size={14} className="animate-spin" /> Scoring photos…
        </div>
      )}

      {error && (
        <p className="text-sm font-mono" style={{ color: '#FF4D4D' }}>{error}</p>
      )}

      {photos.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {photos.map((p, i) => {
            const name = p.path.replace(/\\/g, '/').split('/').pop() ?? p.path
            return (
              <div
                key={p.path}
                className="rounded-xl overflow-hidden group"
                style={{ background: '#161618', border: '1px solid #2A2A2E' }}
              >
                <div className="relative h-36 overflow-hidden" style={{ background: '#2A2A2E' }}>
                  <img
                    src={`file:///${p.path.replace(/\\/g, '/')}`}
                    alt={name}
                    className="w-full h-full object-cover"
                    onError={e => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                  <div className="absolute top-2 left-2">
                    <span
                      className="text-xs font-mono px-1.5 py-0.5 rounded font-medium"
                      style={{ background: '#0D0D0F99', color: '#22C55E' }}
                    >
                      #{i + 1}
                    </span>
                  </div>
                </div>
                <div className="p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-medium" style={{ color: '#22C55E' }}>
                      {p.score.toFixed(0)}/100
                    </span>
                    <button
                      onClick={() => navigator.clipboard.writeText(p.path)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Copy path"
                    >
                      <Copy size={12} style={{ color: '#8A8A96' }} />
                    </button>
                  </div>
                  <p className="text-xs font-mono truncate" style={{ color: '#8A8A96' }}>{name}</p>
                  {p.reason && (
                    <p className="text-xs leading-relaxed" style={{ color: '#8A8A96' }}>{p.reason}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {status === 'complete' && photos.length === 0 && (
        <p className="font-mono text-sm" style={{ color: '#8A8A96' }}>
          No images found in that directory.
        </p>
      )}
    </div>
  )
}
