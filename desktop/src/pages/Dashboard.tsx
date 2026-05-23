import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { HardDrive, Image, BarChart2 } from 'lucide-react'
import { ClutterScoreRing } from '../components/ClutterScoreRing'
import { api, WeeklySnapshot } from '../lib/api'

export function Dashboard() {
  const navigate = useNavigate()
  const [snapshot, setSnapshot] = useState<WeeklySnapshot | null>(null)
  const [backendUp, setBackendUp] = useState(true)

  useEffect(() => {
    api.createSnapshot()
      .then(setSnapshot)
      .catch(() => setBackendUp(false))
  }, [])

  const score = snapshot?.composite_score ?? 0

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-10">
      <div>
        <h1 className="font-serif text-3xl" style={{ color: '#F2F2F3' }}>Declutter AI</h1>
        <p className="font-mono text-sm mt-1" style={{ color: '#8A8A96' }}>
          Privacy-first digital cleanup
        </p>
        {!backendUp && (
          <p className="font-mono text-xs mt-2" style={{ color: '#FF4D4D' }}>
            Backend offline — start the FastAPI server on port 8000
          </p>
        )}
      </div>

      <div className="flex items-center gap-10">
        <ClutterScoreRing score={score} size={160} />
        <div>
          <p className="font-mono text-sm" style={{ color: '#8A8A96' }}>Weekly Clutter Score</p>
          <p className="font-mono text-4xl mt-1" style={{ color: '#F2F2F3' }}>
            {Math.round(score)}
            <span className="text-lg" style={{ color: '#8A8A96' }}>/100</span>
          </p>
          {snapshot && (
            <p className="font-mono text-xs mt-2" style={{ color: '#8A8A96' }}>
              {snapshot.mb_reclaimed.toFixed(0)} MB reclaimed · {snapshot.items_cleared} items cleared this week
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { icon: HardDrive, label: 'Storage',  desc: 'Find duplicates, large & old files', path: '/storage', color: '#7B61FF' },
          { icon: Image,     label: 'Photos',   desc: 'Pick your top 10 aesthetic photos', path: '/photos',  color: '#22C55E' },
          { icon: BarChart2, label: 'Report',   desc: 'Weekly clutter score trend',        path: '/report',  color: '#F59E0B' },
        ].map(({ icon: Icon, label, desc, path, color }) => (
          <button
            key={path}
            onClick={() => navigate(path)}
            className="rounded-xl p-5 text-left transition-all hover:scale-[1.02] active:scale-[0.99]"
            style={{ background: '#161618', border: '1px solid #2A2A2E' }}
          >
            <Icon size={22} style={{ color }} />
            <p className="font-serif text-lg mt-3" style={{ color: '#F2F2F3' }}>{label}</p>
            <p className="font-mono text-xs mt-1" style={{ color: '#8A8A96' }}>{desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
