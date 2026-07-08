'use client'
import { useQuery, useMutation } from '@tanstack/react-query'
import axios from 'axios'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost/api/v1'
export const api = axios.create({ baseURL: API, withCredentials: false })

export type DailySlotCondition = {
  id: number
  condition_type: string
  operator: string
  value: any
  label_pl: string
  label_en: string
}

export type DailySlot = {
  id: number
  position: number
  role: 'top'|'jungle'|'mid'|'adc'|'support'
  label_pl: string
  label_en: string
  conditions: DailySlotCondition[]
}

export type Daily = {
  id: number
  date: string
  status: string
  reveal_mode: string
  slots: DailySlot[]
}

export type Player = {
  id: number
  slug: string
  nickname: string
  real_name: string
  country_code: string
  residency: string
  primary_role: string
  worlds_count: number
  worlds_titles_count: number
  is_active?: boolean
}

export function useDailyToday() {
  return useQuery<Daily>({
    queryKey: ['daily','today'],
    queryFn: async () => (await api.get('/dailies/today/')).data
  })
}

export function usePlayerSearch(q: string, role?: string) {
  return useQuery({
    queryKey: ['players', q, role],
    queryFn: async () => {
      const params:any = { search: q }
      if (role) params.primary_role = role
      const r = await api.get('/players/', { params })
      return r.data.results as Player[]
    },
    enabled: q.length >= 1
  })
}

export function usePlayerAutocomplete(q: string) {
  return useQuery({
    queryKey: ['players-ac', q],
    queryFn: async () => (await api.get('/players/autocomplete/', { params: { q } })).data.results as Player[],
    enabled: q.length >= 1,
    staleTime: 60_000
  })
}

export function useSubmitRoster() {
  return useMutation({
    mutationFn: async (payload: { daily_id: number, guest_token?: string, answers: {slot_id:number, player_slug:string}[] }) => {
      const r = await api.post('/submissions/', payload)
      return r.data
    }
  })
}
