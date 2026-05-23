import { ShieldCheck } from 'lucide-react'

export function ProtectedBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
      style={{ background: '#7B61FF22', color: '#7B61FF', border: '1px solid #7B61FF44' }}
    >
      <ShieldCheck size={12} />
      Protected
    </span>
  )
}
