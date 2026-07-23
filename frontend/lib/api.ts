'use client'
/**
 * Warstwa danych – obsługuje dwa tryby:
 * 1. STATIC (domyślny): dane z /data/*.json (build-time), weryfikacja lokalna
 * 2. API: dane z backendu Django (NEXT_PUBLIC_API_URL), weryfikacja serwerowa
 *
 * Tryb API jest aktywny gdy NEXT_PUBLIC_API_URL jest ustawione.
 */
import { useQuery } from '@tanstack/react-query'

// ------------------------------------------------------------------ typy

export type Role = 'top' | 'jungle' | 'mid' | 'adc' | 'support'

export type DailySlotCondition = {
  id: number
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
  /** [slug, pick_percent] – posortowane malejąco wg popularności (static only) */
  answers: [string, number][]
  /** slug najrzadszego poprawnego picku (diamond) (static only) */
  diamond: string
}

export type Daily = {
  id: number
  date: string
  slots: DailySlot[]
}

export type Player = {
  slug: string
  nickname: string
  real_name: string
  country_code: string
  residency: string
  primary_role: Role
  secondary_roles: Role[]
  worlds_count: number
  is_active: boolean
}

export type ArchiveEntry = { id: number; date: string }

export type RarityTier = 'common' | 'rare' | 'epic' | 'legendary'

export type VerifyResult = {
  is_correct: boolean
  pick_percent: number
  /** odjęcie od 500 – im rzadszy pick, tym większe (lepiej) */
  deduction: number
  rarity_tier: RarityTier | null
  is_diamond_pick: boolean
}

// ------------------------------------------------------------------ config

/**
 * API mode configuration:
 *
 * - NEXT_PUBLIC_API_URL: Direct backend URL (e.g. https://xxx.onrender.com/api/v1)
 *   Used when calling backend directly (needs CORS configured)
 *
 * - NEXT_PUBLIC_USE_API: Set to "true" to enable API mode with proxied requests
 *   When set, API_BASE = '/api/v1' (proxied through Next.js rewrites)
 *   Requires BACKEND_URL env var on the server for the rewrite destination
 *
 * - If neither is set: static JSON mode (no backend needed)
 */
const DIRECT_API = process.env.NEXT_PUBLIC_API_URL || ''
const PROXY_API = process.env.NEXT_PUBLIC_USE_API === 'true' ? '/api/v1' : ''

export const API_BASE = DIRECT_API || PROXY_API
export const USE_API = !!API_BASE

// ------------------------------------------------------------------ daty

export const EPOCH = '2026-01-01' // daily #1

export function todayISO(): string {
  // BUG FIX: Używamy daty LOKALNEJ, nie UTC.
  // new Date().toISOString() zwraca UTC — po północy lokalnie (np. 01:00 CET = 23:00 UTC)
  // gracz zobaczyłby wczorajsze daily zamiast dzisiejszego.
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function daysBetween(a: string, b: string): number {
  return Math.round(
    (new Date(b + 'T12:00:00Z').getTime() - new Date(a + 'T12:00:00Z').getTime()) / 86400000
  )
}

export function dailyIdForDate(date: string): number {
  return daysBetween(EPOCH, date) + 1
}

export function dateForDailyId(id: number): string {
  const d = new Date(EPOCH + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + (id - 1))
  return d.toISOString().slice(0, 10)
}

// ------------------------------------------------------------------ fetch

async function fetchJSON<T>(path: string): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`Nie można pobrać ${path} (${r.status})`)
  return r.json()
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!r.ok) throw new Error(`API error ${r.status} for ${path}`)
  return r.json()
}

// ------------------------------------------------------------------ Daily hooks

export function useDaily(id?: number) {
  return useQuery<Daily>({
    queryKey: ['daily', id],
    queryFn: async () => {
      if (USE_API && id) {
        const data = await apiFetch<any>(`/dailies/${id}/`)
        // Transform backend format to frontend format
        return transformBackendDaily(data)
      }
      return fetchJSON<Daily>(`/data/dailies/${id}.json`)
    },
    enabled: !!id,
    staleTime: USE_API ? 60_000 : Infinity,
  })
}

export function useDailyToday() {
  const today = todayISO()
  const todayId = dailyIdForDate(today)
  // BUG FIX: Include date in query key so cache invalidates at midnight
  return useQuery<Daily>({
    queryKey: ['daily-today', today],
    queryFn: async () => {
      if (USE_API) {
        const data = await apiFetch<any>('/dailies/today/')
        return transformBackendDaily(data)
      }
      return fetchJSON<Daily>(`/data/dailies/${todayId}.json`)
    },
    staleTime: USE_API ? 60_000 : Infinity,
  })
}

/**
 * Wrapper hook for compatibility – returns same shape as before.
 * BUG FIX: Compute dailyId once per hook call, not on every render
 * (todayISO() could return different values across midnight boundary).
 */
export function useDailyTodayCompat() {
  const today = todayISO()
  const result = useDailyToday()
  return { dailyId: dailyIdForDate(today), ...result }
}

// ------------------------------------------------------------------ Players

export function usePlayers() {
  return useQuery<Player[]>({
    queryKey: ['players'],
    queryFn: async () => {
      if (USE_API) {
        // Backend returns paginated results
        const data = await apiFetch<any>('/players/?page_size=1000')
        const results = data.results || data
        return results.map(transformBackendPlayer)
      }
      return fetchJSON<Player[]>('/data/players.json')
    },
    staleTime: USE_API ? 5 * 60_000 : Infinity,
  })
}

// ------------------------------------------------------------------ Archive

export function useArchive() {
  return useQuery<ArchiveEntry[]>({
    queryKey: ['archive'],
    queryFn: async () => {
      if (USE_API) {
        const data = await apiFetch<any>('/dailies/?page_size=365')
        const results = data.results || data
        const today = todayISO()
        return results
          .map((d: any) => ({ id: d.id, date: d.date }))
          .filter((d: ArchiveEntry) => d.date <= today)
          .sort((a: ArchiveEntry, b: ArchiveEntry) => (a.date < b.date ? 1 : -1))
      }
      const idx = await fetchJSON<{ days: ArchiveEntry[] }>('/data/index.json')
      const today = todayISO()
      return idx.days
        .filter(d => d.date <= today)
        .sort((a, b) => (a.date < b.date ? 1 : -1))
    },
    staleTime: 5 * 60_000,
  })
}

// ------------------------------------------------------------------ Backend API: Verify pick (server-side)

export async function verifyPickAPI(dailyId: number, slotId: number, playerSlug: string, guestToken?: string): Promise<VerifyResult & { submission_id?: number }> {
  if (!USE_API) throw new Error('API mode not enabled')
  const body: any = {
    daily_id: dailyId,
    slot_id: slotId,
    player_slug: playerSlug,
  }
  if (guestToken) body.guest_token = guestToken

  const data = await apiFetch<any>('/submissions/answer/', {
    method: 'POST',
    body: JSON.stringify(body),
  })

  return {
    is_correct: data.is_correct,
    pick_percent: data.pick_percent || 0,
    deduction: data.points_awarded || 0,
    rarity_tier: data.rarity_tier || null,
    is_diamond_pick: data.is_diamond_pick || false,
    submission_id: data.id,
  }
}

// ------------------------------------------------------------------ wyszukiwarka (lokalna lub API)

/**
 * Szuka graczy po contiguous substring w nicku lub real_name.
 * Wymaga minimum 2 znaków.
 */
export function searchPlayers(players: Player[] | undefined, q: string, limit = 60): Player[] {
  if (!players) return []
  const needle = q.trim().toLowerCase()
  if (needle.length < 2) return []
  const exact: Player[] = []
  const starts: Player[] = []
  const containsNick: Player[] = []
  const containsReal: Player[] = []
  for (const p of players) {
    const nick = p.nickname.toLowerCase()
    const real = (p.real_name || '').toLowerCase()
    if (nick === needle) {
      exact.push(p)
    } else if (nick.startsWith(needle)) {
      starts.push(p)
    } else if (nick.includes(needle)) {
      containsNick.push(p)
    } else if (real.includes(needle)) {
      containsReal.push(p)
    }
  }
  return [...exact, ...starts, ...containsNick, ...containsReal].slice(0, limit)
}

// ------------------------------------------------------------------ weryfikacja (lokalna – static mode)

export function rarityForPercent(pct: number): RarityTier {
  if (pct > 20) return 'common'
  if (pct > 10) return 'rare'
  if (pct > 1) return 'epic'
  return 'legendary'
}

export function verifyPick(slot: DailySlot, slug: string): VerifyResult {
  const found = slot.answers.find(([s]) => s === slug)
  if (!found) {
    return { is_correct: false, pick_percent: 0, deduction: 0, rarity_tier: null, is_diamond_pick: false }
  }
  const pct = found[1]
  const diamond = slot.diamond === slug
  const deduction = diamond ? 100 : Math.round((100 - pct) * 10) / 10
  return {
    is_correct: true,
    pick_percent: pct,
    deduction,
    rarity_tier: rarityForPercent(pct),
    is_diamond_pick: diamond,
  }
}

// ------------------------------------------------------------------ scoring

export const START_SCORE = 500
export const MAX_ERRORS = 10

// ------------------------------------------------------------------ backend transformers

function transformBackendDaily(data: any): Daily {
  return {
    id: data.id,
    date: data.date,
    slots: (data.slots || []).map((s: any) => ({
      id: s.id,
      position: s.position,
      role: s.role,
      label_pl: s.label_pl || s.role,
      label_en: s.label_en || s.role,
      conditions: (s.conditions || []).map((c: any) => ({
        id: c.id,
        label_pl: c.label_pl,
        label_en: c.label_en,
      })),
      // Backend doesn't serve answers (security) – empty for API mode
      // Verification happens server-side via /submissions/answer/
      answers: s.answers || [],
      diamond: s.diamond || '',
    })),
  }
}

function transformBackendPlayer(data: any): Player {
  return {
    slug: data.slug,
    nickname: data.nickname,
    real_name: data.real_name || '',
    country_code: data.country_code || '',
    residency: data.residency || '',
    primary_role: data.primary_role || 'mid',
    secondary_roles: data.secondary_roles || [],
    worlds_count: data.worlds_count || 0,
    is_active: data.is_active ?? true,
  }
}
