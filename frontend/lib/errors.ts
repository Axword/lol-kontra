import axios from 'axios'

export function formatApiError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback
  const message = (value: unknown): string | undefined => {
    if (typeof value === 'string') return value
    if (Array.isArray(value)) return value.map(message).filter(Boolean).join(' ') || undefined
    if (value && typeof value === 'object') {
      const fields = value as Record<string, unknown>
      return message(fields.detail) || message(fields.non_field_errors) ||
        Object.values(fields).map(message).filter(Boolean).join(' ') || undefined
    }
  }
  return message(error.response?.data) || fallback
}

/** Missing boards should not wait through automatic network retries. */
export function retryApiQuery(failureCount: number, error: unknown) {
  if (axios.isAxiosError(error) && error.response && error.response.status < 500 && error.response.status !== 429) return false
  return failureCount < 2
}
