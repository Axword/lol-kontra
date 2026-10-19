'use client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { isValidDailyId, useGameDate } from './daily'
export { formatApiError } from './errors'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
export const api = axios.create({ baseURL: API, withCredentials: false })

/* ------------------------------------------------------------------ */
/*  Typy                                                               */
/* ------------------------------------------------------------------ */

export type Role = 'top' | 'jungle' | 'mid' | 'adc' | 'support'
export type RarityTier = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary'

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
  role: Role
  label_pl: string
  label_en: string
  conditions: DailySlotCondition[]
}

export type Daily = {
  id: number
  date: string
  status: string
  slots: DailySlot[]
}

export type Player = {
  id: number
  slug: string
  nickname: string
  portrait_url?: string | null
  real_name: string
  country_code: string
  residency: string
  primary_role: Role
  is_active?: boolean
  /** Nie zwracane przez autocomplete – to dane, na których opiera się weryfikacja warunków. */
  worlds_count?: number
  worlds_titles_count?: number
}

export type GameAnswer = {
  id: number
  daily_slot: number
  slot_role: Role
  player: number
  player_nickname: string
  player_slug: string
  player_portrait_url?: string | null
  is_correct: boolean
  rarity_tier: RarityTier | null
  rarity_percent: number | null
  points_awarded: number
  deduction?: number
  is_diamond_pick: boolean
}

/**
 * Pełny stan gry. Wszystkie liczniki pochodzą z serwera – frontend niczego nie dolicza
 * i nie trzyma własnej kopii limitu błędów.
 */
export type GameState = {
  id: number | null
  daily: number
  total_points: number
  is_scored: boolean
  is_practice?: boolean
  errors_used: number
  errors_left: number
  max_errors: number
  slots_total: number
  correct_count: number
  is_over: boolean
  answers: GameAnswer[]
}

/** Odpowiedź serwera na pojedynczą próbę: sprawdzony wybór + pełny stan gry. */
export type AnswerResult = GameAnswer & {
  /** Authoritative answers also reconcile moves made in another open window. */
  answers?: GameAnswer[]
  /** Udział wyborów tego zawodnika na tym slocie. `null`, gdy odpowiedź jest błędna. */
  pick_percent: number | null
  pick_count: number | null
  sample_size: number | null
  /** Próba jest jeszcze zbyt mała, żeby rzadkość uznać za ostateczną. */
  is_provisional: boolean
  /** Slot był już zamknięty – nic się nie zmieniło. */
  unchanged: boolean
  guest_token?: string
  submission_id: number

  total_points: number
  errors_used: number
  errors_left: number
  max_errors: number
  slots_total: number
  correct_count: number
  is_over: boolean
  is_scored?: boolean
  is_practice?: boolean
}

/* ------------------------------------------------------------------ */
/*  Zapytania                                                          */
/* ------------------------------------------------------------------ */

export function useDailyToday() {
  const date = useGameDate()
  return useQuery<Daily>({
    queryKey: ['daily', 'today', date],
    queryFn: async ({ signal }) => (await api.get('/dailies/today/', { signal })).data,
    staleTime: 5 * 60_000,
  })
}

export function useDaily(dailyId?: number) {
  return useQuery<Daily>({
    queryKey: ['daily', dailyId],
    queryFn: async ({ signal }) => (await api.get(`/dailies/${dailyId}/`, { signal })).data,
    enabled: isValidDailyId(dailyId),
  })
}

export const gameStateKey = (dailyId?: number, guestToken?: string, date?: string) => ['game-state', dailyId, guestToken || '', date] as const

/**
 * Stan gry. Bez odpytywania w pętli – stan zmienia się wyłącznie w reakcji na ruch
 * gracza, a odpowiedź mutacji od razu aktualizuje cache.
 */
export function useGameState(dailyId?: number, guestToken?: string) {
  const date = useGameDate()
  return useQuery<GameState>({
    queryKey: gameStateKey(dailyId, guestToken, date),
    queryFn: async ({ signal }) => {
      const params: Record<string, string> = { daily_id: String(dailyId) }
      if (guestToken) params.guest_token = guestToken
      return (await api.get('/submissions/me/', { params, signal })).data
    },
    enabled: isValidDailyId(dailyId) && !!guestToken?.trim(),
    staleTime: 30_000,
    refetchOnWindowFocus: 'always',
  })
}

export function useAnswerSlot(dailyId?: number) {
  const qc = useQueryClient()
  const date = useGameDate()
  return useMutation<AnswerResult, unknown, { slot_id: number; player_slug: string; guest_token: string }, { dailyId: number; key: ReturnType<typeof gameStateKey> }>({
    mutationFn: async (payload) => {
      if (!isValidDailyId(dailyId) || !payload.guest_token.trim()) throw new Error('Missing game identity')
      const r = await api.post('/submissions/answer/', { daily_id: dailyId, ...payload })
      return r.data
    },
    onMutate: async (payload) => {
      if (!isValidDailyId(dailyId)) throw new Error('Invalid daily')
      const key = gameStateKey(dailyId, payload.guest_token, date)
      await qc.cancelQueries({ queryKey: key, exact: true })
      return { dailyId, key }
    },
    onSuccess: async (data, _payload, context) => {
      if (!context) return
      await qc.cancelQueries({ queryKey: context.key, exact: true })
      // Odpowiedź zawiera komplet stanu gry – nadpisujemy cache bez dodatkowego GET-a.
      qc.setQueryData<GameState>(context.key, (prev) => {
        const answers = [...(data.answers ?? prev?.answers ?? [])]
        const idx = answers.findIndex((a) => a.daily_slot === data.daily_slot)
        const answer: GameAnswer = {
          id: data.id,
          daily_slot: data.daily_slot,
          slot_role: data.slot_role,
          player: data.player,
          player_nickname: data.player_nickname,
          player_slug: data.player_slug,
          player_portrait_url: data.player_portrait_url,
          is_correct: data.is_correct,
          rarity_tier: data.rarity_tier,
          rarity_percent: data.rarity_percent,
          points_awarded: data.points_awarded,
          deduction: data.deduction,
          is_diamond_pick: data.is_diamond_pick,
        }
        if (idx >= 0) answers[idx] = answer
        else answers.push(answer)
        return {
          id: data.submission_id ?? prev?.id ?? null,
          daily: context.dailyId,
          total_points: data.total_points,
          is_scored: data.is_scored ?? prev?.is_scored ?? false,
          is_practice: data.is_practice ?? prev?.is_practice ?? false,
          errors_used: data.errors_used,
          errors_left: data.errors_left,
          max_errors: data.max_errors,
          slots_total: data.slots_total,
          correct_count: data.correct_count,
          is_over: data.is_over,
          answers,
        }
      })
      void qc.invalidateQueries({ queryKey: ['answer-stats', context.dailyId] })
      void qc.invalidateQueries({ queryKey: ['score-distribution', context.dailyId] })
      void qc.invalidateQueries({ queryKey: ['leaderboard'] })
      if (data.is_over) void qc.invalidateQueries({ queryKey: ['guest-profile', _payload.guest_token] })
      if (data.is_over) void qc.invalidateQueries({ queryKey: ['daily-community', context.dailyId] })
    },
    onError: (_error, _payload, context) => {
      // A response can be lost after the server committed a move. Refresh before
      // retrying, including when another tab has already finished the board.
      if (context) void qc.invalidateQueries({ queryKey: context.key, exact: true })
    },
  })
}

export function usePlayerAutocomplete(q: string) {
  return useQuery<Player[]>({
    queryKey: ['players-ac', q],
    queryFn: async ({ signal }) => {
      const params = { q: q.trim() }
      return (await api.get('/players/autocomplete/', { params, signal })).data.results
    },
    enabled: q.trim().length >= 1,
    staleTime: 60_000,
  })
}

export type SolutionPlayer = Player & { pick_count: number; pick_percent: number }
export type AnswerPickStat = { slot_id: number; player_slug: string; pick_percent: number }

export function useAnswerStats(dailyId: number, enabled: boolean) {
  return useQuery<{ results: AnswerPickStat[] }>({
    queryKey: ['answer-stats', dailyId],
    queryFn: async ({ signal }) => (await api.get(`/dailies/${dailyId}/answer-stats/`, { signal })).data,
    enabled: enabled && isValidDailyId(dailyId),
    staleTime: 30_000,
  })
}

export type DailySolutions = {
  daily_id: number
  slots: { slot_id: number; role: Role; sample_size: number; players: SolutionPlayer[] }[]
  popular: Record<string, number>
  rare: Record<string, number>
}

export function useDailySolutions(dailyId: number, guestToken: string) {
  return useQuery<DailySolutions>({
    queryKey: ['solutions', dailyId, guestToken],
    queryFn: async ({ signal }) => (await api.get(`/dailies/${dailyId}/solutions/`, {
      params: { guest_token: guestToken }, signal,
    })).data,
    enabled: isValidDailyId(dailyId) && !!guestToken,
  })
}

export function useScoreDistribution(dailyId?: number, userScore?: number, enabled = true) {
  return useQuery({
    queryKey: ['score-distribution', dailyId, userScore],
    queryFn: async () => {
      const params: any = {}
      if (userScore != null) params.user_score = userScore
      return (await api.get(`/dailies/${dailyId}/score-distribution/`, { params })).data
    },
    enabled: isValidDailyId(dailyId) && enabled,
    staleTime: 30_000,
  })
}

export function useLeaderboard(dailyId?: number, enabled = true) {
  return useQuery({
    queryKey: ['leaderboard', dailyId ?? 'all'],
    queryFn: async () =>
      (await api.get('/leaderboard/', { params: dailyId ? { daily_id: dailyId } : {} })).data,
    enabled: enabled && (dailyId == null || isValidDailyId(dailyId)),
    staleTime: 60_000,
  })
}

export function useArchive() {
  const date = useGameDate()
  return useQuery({
    queryKey: ['dailies', 'archive', date],
    queryFn: async () =>
      (await api.get('/dailies/', { params: { ordering: '-date', page_size: 42 } })).data,
    staleTime: 5 * 60_000,
  })
}

/* Zbiorcze wysłanie składu – używane w archiwum. */
export function useSubmitRoster() {
  return useMutation({
    mutationFn: async (payload: {
      daily_id: number
      guest_token?: string
      answers: { slot_id: number; player_slug: string }[]
    }) => (await api.post('/submissions/', payload)).data,
  })
}
