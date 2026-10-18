'use client'
import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { retryApiQuery } from './errors'
import { usePrefs } from './store'

export type GuestProfile = {
  nickname: string | null
  display_name: string
  stats: {
    games_played: number
    total_points: number
    avg_points: number
    best_score: number
    legendary_answers: number
    diamond_picks: number
    current_streak: number
    max_streak: number
  }
}

export const guestProfileKey = (guestToken: string) => ['guest-profile', guestToken] as const

export function useGuestToken() {
  const token = usePrefs((state) => state.guestToken)
  const ensureGuestToken = usePrefs((state) => state.ensureGuestToken)
  useEffect(() => { if (!token) ensureGuestToken() }, [token, ensureGuestToken])
  return token
}

export function useGuestProfile(guestToken: string) {
  return useQuery<GuestProfile>({
    queryKey: guestProfileKey(guestToken),
    queryFn: async ({ signal }) => (await api.post('/guest/profile/', { guest_token: guestToken }, { signal })).data,
    enabled: !!guestToken,
    staleTime: 60_000,
    retry: retryApiQuery,
  })
}

export function useUpdateGuestNickname() {
  const client = useQueryClient()
  return useMutation<GuestProfile, unknown, { guest_token: string; nickname: string }>({
    mutationFn: async (payload) => (await api.post('/guest/profile/', payload)).data,
    onMutate: async ({ guest_token }) => {
      await client.cancelQueries({ queryKey: guestProfileKey(guest_token) })
    },
    onSuccess: (profile, { guest_token }) => {
      client.setQueryData(guestProfileKey(guest_token), profile)
      void client.invalidateQueries({ queryKey: ['leaderboard'] })
    },
  })
}
