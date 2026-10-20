'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import { useGameDate } from './daily'

export type ChallengeProgress = { results: { daily_id: number; completed: boolean }[] }
export function useChallengeProgress(guestToken: string) {
  const date = useGameDate()
  return useQuery<ChallengeProgress>({
    queryKey: ['challenge-progress', guestToken, date],
    queryFn: async ({ signal }) => (await api.post('/dailies/progress/', { guest_token: guestToken }, { signal })).data,
    enabled: !!guestToken,
    staleTime: 30_000,
    refetchOnWindowFocus: 'always',
  })
}

export function completedDaily(data: ChallengeProgress | undefined, id: number): boolean | undefined {
  return data ? data.results.some(row => row.daily_id === id && row.completed) : undefined
}
