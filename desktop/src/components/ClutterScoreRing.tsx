import { scoreColor } from '../lib/tokens'

type Props = { score: number; size?: number }

export function ClutterScoreRing({ score, size = 160 }: Props) {
  const radius = (size - 20) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(100, score))
  const dashOffset = circumference * (1 - pct / 100)
  const color = scoreColor(pct)

  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke="#2A2A2E" strokeWidth={12}
      />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none" stroke={color} strokeWidth={12}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text
        x="50%" y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        style={{
          transform: 'rotate(90deg)',
          transformOrigin: '50% 50%',
          fill: color,
          fontSize: size * 0.22,
          fontFamily: 'DM Mono',
          fontWeight: 500,
        }}
      >
        {Math.round(pct)}
      </text>
    </svg>
  )
}
