import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { api, WeeklySnapshot } from '../lib/api'

export function ReportPage() {
  const [weeks, setWeeks] = useState<WeeklySnapshot[]>([])

  useEffect(() => {
    api.getWeeklyReport().then(setWeeks).catch(() => {})
  }, [])

  const data = weeks.map(w => ({
    week:  w.week_start.slice(5),    // "MM-DD"
    score: Math.round(w.composite_score),
    mb:    Math.round(w.mb_reclaimed),
  }))

  const tooltipStyle = {
    background: '#161618',
    border: '1px solid #2A2A2E',
    fontFamily: 'DM Mono',
    fontSize: 12,
    color: '#F2F2F3',
  }

  const tickStyle = { fill: '#8A8A96', fontSize: 11, fontFamily: 'DM Mono' }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-10">
      <div>
        <h1 className="font-serif text-2xl" style={{ color: '#F2F2F3' }}>Weekly Report</h1>
        <p className="font-mono text-sm mt-1" style={{ color: '#8A8A96' }}>
          Last 8 weeks of clutter activity
        </p>
      </div>

      <div
        className="rounded-xl p-6 space-y-4"
        style={{ background: '#161618', border: '1px solid #2A2A2E' }}
      >
        <p className="font-mono text-sm" style={{ color: '#8A8A96' }}>Composite Clutter Score</p>
        {data.length === 0 ? (
          <p className="font-mono text-xs" style={{ color: '#8A8A96' }}>
            No data yet — run a scan and confirm some items to populate the report.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2E" />
              <XAxis dataKey="week" tick={tickStyle} />
              <YAxis domain={[0, 100]} tick={tickStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line
                type="monotone" dataKey="score"
                stroke="#7B61FF" strokeWidth={2}
                dot={{ fill: '#7B61FF', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div
        className="rounded-xl p-6 space-y-4"
        style={{ background: '#161618', border: '1px solid #2A2A2E' }}
      >
        <p className="font-mono text-sm" style={{ color: '#8A8A96' }}>MB Reclaimed per Week</p>
        {data.length === 0 ? (
          <p className="font-mono text-xs" style={{ color: '#8A8A96' }}>
            No data yet.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2E" />
              <XAxis dataKey="week" tick={tickStyle} />
              <YAxis tick={tickStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="mb" fill="#22C55E" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
