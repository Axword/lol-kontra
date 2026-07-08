import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type AnswerResult = {
  is_correct?: boolean
  rarity_tier?: 'common' | 'rare' | 'epic' | 'legendary' | null
  points_awarded?: number   // now = deduction (e.g. 95.8)
  pick_percent?: number
  is_diamond_pick?: boolean
  locked?: boolean
}

type Pick = { 
  slotId: number, 
  playerSlug?: string, 
  playerNickname?: string 
} & AnswerResult

type RosterState = {
  dailyId?: number
  picks: Record<number, Pick>
  submitted: boolean
  guestToken: string
  errors: number
  maxErrors: number
  setPick: (slotId: number, playerSlug: string, playerNickname: string) => void
  setAnswer: (slotId: number, ans: AnswerResult) => void
  clearPick: (slotId: number) => void
  incrementError: () => void
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
      errors: 0,
      maxErrors: 10,

      setPick: (slotId, playerSlug, playerNickname) => set(state => {
        const prev = state.picks[slotId] || { slotId }
        // only block if CORRECTLY locked
        if (prev.locked && prev.is_correct === true) return state
        return {
          picks: { ...state.picks, [slotId]: { ...prev, slotId, playerSlug, playerNickname } }
        }
      }),

      setAnswer: (slotId, ans) => set(state => {
        const prev = state.picks[slotId] || { slotId }
        // LOCK only if correct
        const isCorrect = !!ans.is_correct
        const locked = isCorrect
        return {
          picks: { 
            ...state.picks, 
            [slotId]: { 
              ...prev, 
              ...ans, 
              locked 
            } 
          }
        }
      }),

      clearPick: (slotId) => set(state => {
        const prev = state.picks[slotId]
        // cannot clear a correctly locked slot
        if (prev?.locked && prev.is_correct === true) return state
        const n = { ...state.picks }
        delete n[slotId]
        return { picks: n }
      }),

      incrementError: () => set(state => ({
        errors: Math.min(state.errors + 1, state.maxErrors)
      })),

      setDaily: (id) => {
        const s = get()
        if (s.dailyId !== id) {
          set({ 
            dailyId: id, 
            picks: {}, 
            submitted: false,
            errors: 0 
          })
        }
      },

      markSubmitted: () => set({ submitted: true }),
      reset: () => set({ picks: {}, submitted: false, errors: 0 })
    }),
    { name: 'lol-roster-store' }
  )
)
