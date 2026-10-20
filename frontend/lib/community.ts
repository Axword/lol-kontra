'use client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { isValidDailyId, useGameDate } from './daily'
import { retryApiQuery } from './errors'
import { SupportedTeam } from './guest-profile'
import type { Locale } from './locale'

export type CommunityComment = {
  id: number
  nickname: string
  team: SupportedTeam | null
  score: number
  created_at: string
  text: string | null
  roster_image_url: string | null
}

export type DailyCommunity = {
  author: { name: string; url: string; description: string; avatar_url?: string }
  can_view_solutions: boolean
  can_comment?: boolean
  comments: CommunityComment[]
  player_ranking: { nickname: string; team: SupportedTeam | null; score: number }[]
  team_ranking: { team: SupportedTeam; players: number; average_score: number }[]
}

export const communityKey = (dailyId: number, token: string, date: string) => ['daily-community', dailyId, token, date] as const

export function useDailyCommunity(dailyId: number, token: string, enabled = true) {
  const date = useGameDate()
  return useQuery<DailyCommunity>({
    queryKey: communityKey(dailyId, token, date),
    queryFn: async ({ signal }) => token
      ? (await api.post(`/dailies/${dailyId}/community/`, { guest_token: token }, { signal })).data
      : (await api.get(`/dailies/${dailyId}/community/`, { signal })).data,
    enabled: enabled && isValidDailyId(dailyId),
    staleTime: 30_000,
    retry: retryApiQuery,
  })
}

export function usePostCommunityComment(dailyId: number, token: string) {
  const date = useGameDate()
  const client = useQueryClient()
  const key = communityKey(dailyId, token, date)
  return useMutation<DailyCommunity, unknown, string>({
    mutationFn: async (comment) => {
      if (!isValidDailyId(dailyId) || !token || !comment.trim()) throw new Error('Missing comment identity')
      return (await api.post(`/dailies/${dailyId}/community/`, { guest_token: token, comment })).data
    },
    onMutate: async () => { await client.cancelQueries({ queryKey: key, exact: true }) },
    onSuccess: (data) => { client.setQueryData(key, data) },
  })
}

/** Root-relative share paths belong to Django, including when it is hosted separately. */
export function communityImageUrl(path: string | null, locale?: Locale) {
  if (!path) return null
  try {
    const base = api.defaults.baseURL || 'http://localhost:8000/api/v1'
    const url = new URL(path, `${base.replace(/\/$/u, '')}/`)
    if (locale && /^\/api\/v1\/roster-shares\/[^/]+\.png$/u.test(url.pathname)) {
      url.searchParams.set('v', '2')
      url.searchParams.set('lang', locale)
    }
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch { return null }
}
