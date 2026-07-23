'use client'
/**
 * Frontendowa warstwa danych – zero backendu.
 * Wszystkie dane pochodzą ze statycznych plików JSON generowanych
 * podczas builda przez scripts/generate-data.mjs (public/data/).
 * Weryfikacja odpowiedzi odbywa się lokalnie w przeglądarce.
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
  /** [slug, pick_percent] – posortowane malejąco wg popularności */
  answers: [string, number][]
  /** slug najrzadszego poprawnego picku (diamond) */
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

// ------------------------------------------------------------------ daty

export const EPOCH = '2026-01-01' // daily #1

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
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

export function useDaily(id?: number) {
  return useQuery<Daily>({
    queryKey: ['daily', id],
    queryFn: () => fetchJSON<Daily>(`/data/dailies/${id}.json`),
    enabled: !!id,
    staleTime: Infinity,
  })
}

export function useDailyToday() {
  const id = dailyIdForDate(todayISO())
  return { dailyId: id, ...useDaily(id) }
}

export function usePlayers() {
  return useQuery<Player[]>({
    queryKey: ['players'],
    queryFn: () => fetchJSON<Player[]>('/data/players.json'),
    staleTime: Infinity,
  })
}

export function useArchive() {
  return useQuery<ArchiveEntry[]>({
    queryKey: ['archive'],
    queryFn: async () => {
      const idx = await fetchJSON<{ days: ArchiveEntry[] }>('/data/index.json')
      const today = todayISO()
      return idx.days
        .filter(d => d.date <= today)
        .sort((a, b) => (a.date < b.date ? 1 : -1))
    },
    staleTime: 5 * 60_000,
  })
}

// ------------------------------------------------------------------ wyszukiwarka (lokalna)

export function searchPlayers(players: Player[] | undefined, q: string, limit = 60): Player[] {
  if (!players) return []
  const needle = q.trim().toLowerCase()
  if (!needle) return []
  const starts: Player[] = []
  const contains: Player[] = []
  for (const p of players) {
    const nick = p.nickname.toLowerCase()
    const real = (p.real_name || '').toLowerCase()
    if (nick.startsWith(needle)) starts.push(p)
    else if (nick.includes(needle) || real.includes(needle)) contains.push(p)
    if (starts.length >= limit) break
  }
  return [...starts, ...contains].slice(0, limit)
}

// ------------------------------------------------------------------ weryfikacja (lokalna)

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
