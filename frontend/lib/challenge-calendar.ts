'use client'
import { useInfiniteQuery } from '@tanstack/react-query'
import { api, Daily } from './api'

export function useChallengeCalendar(date: string) {
  return useInfiniteQuery({
    queryKey: ['dailies', 'calendar', date],
    initialPageParam: 1,
    queryFn: async ({ pageParam, signal }) => (await api.get<{results: Daily[]; next: string | null}>('/dailies/', {
      params: { ordering: '-date', page: pageParam }, signal,
    })).data,
    getNextPageParam: (last, pages) => last.next ? pages.length + 1 : undefined,
    staleTime: 5 * 60_000,
  })
}
