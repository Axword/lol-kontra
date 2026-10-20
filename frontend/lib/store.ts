import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * Store trzyma wyłącznie preferencje i tożsamość gościa.
 * Ustawienie dźwięku mieszka w `lib/sound.ts` – nie duplikujemy go tutaj.
 *
 * Stan rozgrywki (wybory, punkty, błędy) NIE jest tu duplikowany – jego jedynym
 * źródłem jest serwer (`/submissions/me/`). Wcześniejsza wersja trzymała równoległą
 * kopię w localStorage, przez co po północy widać było wczorajszą planszę,
 * a licznik błędów rozjeżdżał się z serwerem.
 */
type Prefs = {
  guestToken: string
  locale: 'pl' | 'en'
  seenHelp: boolean
  setLocale: (l: 'pl' | 'en') => void
  markHelpSeen: () => void
  ensureGuestToken: () => string
}

function randomToken() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export const usePrefs = create<Prefs>()(
  persist(
    (set, get) => ({
      guestToken: '',
      locale: 'pl',
      seenHelp: false,

      setLocale: (locale) => set({ locale }),
      markHelpSeen: () => set({ seenHelp: true }),

      ensureGuestToken: () => {
        const current = get().guestToken
        if (current) return current
        const token = randomToken()
        set({ guestToken: token })
        return token
      },
    }),
    {
      name: 'worldsxi-prefs',
      // Game/profile hooks create identities explicitly. Migration pages must
      // inspect the existing identity before creating or replacing one.
    }
  )
)
