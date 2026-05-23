export const tokens = {
  bg:            '#0D0D0F',
  surface:       '#161618',
  border:        '#2A2A2E',
  accent:        '#7B61FF',
  danger:        '#FF4D4D',
  success:       '#22C55E',
  warning:       '#F59E0B',
  textPrimary:   '#F2F2F3',
  textSecondary: '#8A8A96',
} as const

export function scoreColor(score: number): string {
  if (score < 40) return tokens.danger
  if (score < 70) return tokens.warning
  return tokens.success
}
