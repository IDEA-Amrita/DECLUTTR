import { useCallback, Dispatch, SetStateAction } from 'react'
import { api, FileSuggestion } from '../lib/api'

export function useConsent(
  setSuggestions: Dispatch<SetStateAction<FileSuggestion[]>>
) {
  const confirm = useCallback(async (suggestion: FileSuggestion) => {
    const result = await api.confirmConsent(
      suggestion.id, 'storage', suggestion.action, true
    )
    if (result.executed) {
      setSuggestions(prev => prev.filter(s => s.id !== suggestion.id))
    }
    return result
  }, [setSuggestions])

  const skip = useCallback((id: string) => {
    setSuggestions(prev => prev.filter(s => s.id !== id))
  }, [setSuggestions])

  return { confirm, skip }
}
