import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type AnswerResult = {
  is_correct?: boolean
  rarity_tier?: 'common' | 'rare' | 'epic' | 'legendary' | null
  points_awarded?: number
  is_diamond_pick?: boolean
  locked?: boolean
}

type Pick = { slotId: number, playerSlug?: string, playerNickname?: string } & AnswerResult

type RosterState = {
  dailyId?: number
  picks: Record<number, Pick>
  submitted: boolean
  guestToken: string
  setPick: (slotId: number, playerSlug: string, playerNickname: string) => void
  setAnswer: (slotId: number, ans: AnswerResult) => void
  clearPick: (slotId: number) => void
  setDaily: (id: number) => void
  markSubmitted: () => void
  reset: () => void
}

function genGuestToken() {
  if (typeof window === 'undefined') return 'srv'
  let t = localStorage.getItem('guest_token')
  if (!t) {
    t = Math.random().toString(36).slice(2) + Date.now().toString(36)
    localStorage.setItem('guest_token', t)
  }
  return t
}

export const useRosterStore = create<RosterState>()(
  persist(
    (set, get) => ({
      dailyId: undefined,
      picks: {},
      submitted: false,
      guestToken: typeof window !== 'undefined' ? genGuestToken() : '',
      setPick: (slotId, playerSlug, playerNickname) => set(state => {
        const prev = state.picks[slotId] || { slotId }
        // if locked – ignore
        if (prev.locked) return state
        return {
          picks: { ...state.picks, [slotId]: { ...prev, slotId, playerSlug, playerNickname } }
        }
      }),
      setAnswer: (slotId, ans) => set(state => {
        const prev = state.picks[slotId] || { slotId }
        return {
          picks: { ...state.picks, [slotId]: { ...prev, ...ans, locked: true } }
        }
      }),
      clearPick: (slotId) => set(state => {
        const prev = state.picks[slotId]
        if (prev?.locked) return state // cannot clear locked
        const n = { ...state.picks }
        delete n[slotId]
        return { picks: n }
      }),
      setDaily: (id) => {
        const s = get()
        if (s.dailyId !== id) {
          set({ dailyId: id, picks: {}, submitted: false })
        }
      },
      markSubmitted: () => set({ submitted: true }),
      reset: () => set({ picks: {}, submitted: false })
    }),
    { name: 'lol-roster-store' }
  )
)
