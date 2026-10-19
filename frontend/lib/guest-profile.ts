'use client'
import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import { retryApiQuery } from './errors'
import { usePrefs } from './store'

export type SupportedTeam = {
  id: string
  code: string
  name: string
  region: string
  logo_url: string
}

export type ProfilePlayer = {
  id: number
  slug: string
  nickname: string
  portrait_url: string | null
  pick_count: number
}

export type GuestProfile = {
  nickname: string | null
  has_custom_nickname?: boolean
  display_name: string
  supported_team?: SupportedTeam | null
  stats: {
    games_played: number
    total_points: number
    avg_points: number
    best_score: number
    legendary_answers: number
    diamond_picks: number
    current_streak: number
    max_streak: number
    correct_answers?: number
    incorrect_attempts?: number
    accuracy_percent?: number
    perfect_games?: number
    average_pick_percent?: number
    most_used_player?: ProfilePlayer | null
    top_players?: ProfilePlayer[]
  }
}

export type WorldsTeams = { season: number; teams: SupportedTeam[]; source_url: string }

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
  return useUpdateGuestProfile<{ guest_token: string; nickname: string }>()
}

export function useUpdateSupportedTeam() {
  return useUpdateGuestProfile<{ guest_token: string; supported_team: string | null }>()
}

function useUpdateGuestProfile<Payload extends { guest_token: string }>() {
  const client = useQueryClient()
  return useMutation<GuestProfile, unknown, Payload>({
    scope: { id: 'guest-profile-update' },
    mutationFn: async (payload) => (await api.post('/guest/profile/', payload)).data,
    onMutate: async ({ guest_token }) => {
      await client.cancelQueries({ queryKey: guestProfileKey(guest_token) })
    },
    onSuccess: (profile, { guest_token }) => {
      client.setQueryData(guestProfileKey(guest_token), profile)
      void client.invalidateQueries({ queryKey: ['leaderboard'] })
      void client.invalidateQueries({ queryKey: ['daily-community'] })
    },
  })
}

export function useWorldsTeams(enabled = true) {
  return useQuery<WorldsTeams>({
    queryKey: ['worlds-teams', 2026],
    queryFn: async ({ signal }) => (await api.get('/guest/teams/', { signal })).data,
    enabled,
    staleTime: 60 * 60_000,
    retry: retryApiQuery,
  })
}
