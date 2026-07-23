import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { MAX_ERRORS, START_SCORE, RarityTier } from './api'

export type Pick = {
  slotId: number
  playerSlug: string
  playerNickname: string
  is_correct: boolean
  rarity_tier: RarityTier | null
  /** odjęcie od 500 (tylko dla trafień) */
  deduction: number
  pick_percent: number
  is_diamond_pick: boolean
  locked: boolean
}

export type GameState = {
  picks: Record<number, Pick>
  errors: number
  finished: boolean
  /** wynik końcowy: 500 - suma odjęć (niższy = lepszy) */
  score: number | null
  finishedAt?: string
  date?: string
}

const emptyGame = (): GameState => ({
  picks: {},
  errors: 0,
  finished: false,
  score: null,
})

type Store = {
  games: Record<number, GameState>
  applyPick: (dailyId: number, pick: Pick, totalSlots: number, date?: string) => void
  clearPick: (dailyId: number, slotId: number) => void
  resetGame: (dailyId: number) => void
}

function computeScore(game: GameState): number {
  const total = Object.values(game.picks)
    .filter(p => p.is_correct)
    .reduce((s, p) => s + p.deduction, 0)
  return Math.round((START_SCORE - total) * 10) / 10
}

export const useGameStore = create<Store>()(
  persist(
    (set) => ({
      games: {},

      applyPick: (dailyId, pick, totalSlots, date) => set(state => {
        const game = state.games[dailyId] ?? emptyGame()
        if (game.finished) return state
        const prev = game.picks[pick.slotId]
        if (prev?.locked && prev.is_correct) return state

        const picks = { ...game.picks, [pick.slotId]: pick }
        const errors = pick.is_correct ? game.errors : Math.min(game.errors + 1, MAX_ERRORS)
        const correct = Object.values(picks).filter(p => p.is_correct).length
        const finished = correct >= totalSlots || errors >= MAX_ERRORS
        const next: GameState = {
          ...game,
          picks,
          errors,
          finished,
          date: date ?? game.date,
          score: finished ? computeScore({ ...game, picks }) : game.score,
          finishedAt: finished ? new Date().toISOString() : game.finishedAt,
        }
        return { games: { ...state.games, [dailyId]: next } }
      }),

      clearPick: (dailyId, slotId) => set(state => {
        const game = state.games[dailyId]
        if (!game || game.finished) return state
        const prev = game.picks[slotId]
        if (prev?.locked && prev.is_correct) return state
        const picks = { ...game.picks }
        delete picks[slotId]
        return { games: { ...state.games, [dailyId]: { ...game, picks } } }
      }),

      resetGame: (dailyId) => set(state => {
        const games = { ...state.games }
        delete games[dailyId]
        return { games }
      }),
    }),
    { name: 'worlds-xi-games-v2' }
  )
)

export function useGame(dailyId?: number): GameState {
  const game = useGameStore(s => (dailyId != null ? s.games[dailyId] : undefined))
  return game ?? emptyGame()
}
