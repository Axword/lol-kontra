import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { deviceLocale, type Locale } from './locale'

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
  locale: Locale
  localePreference: 'auto' | Locale
  seenHelp: boolean
  setLocale: (l: Locale) => void
  syncDeviceLocale: () => void
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
      locale: 'en',
      localePreference: 'auto',
      seenHelp: false,

      setLocale: (locale) => set({ locale, localePreference: locale }),
      syncDeviceLocale: () => {
        if (get().localePreference === 'auto') set({ locale: deviceLocale() })
      },
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
      merge: (persisted, current) => {
        const saved = persisted as Partial<Prefs> | undefined
        // Before device detection, PL was saved for everyone. Only a legacy EN
        // value proves a deliberate choice. Preserve identities and help state.
        const preference = saved?.localePreference === 'pl' || saved?.localePreference === 'en' || saved?.localePreference === 'auto'
          ? saved.localePreference : saved?.locale === 'en' ? 'en' : 'auto'
        return { ...current, ...saved, localePreference: preference,
          locale: preference === 'auto' ? deviceLocale() : preference }
      },
      // Game/profile hooks create identities explicitly. Migration pages must
      // inspect the existing identity before creating or replacing one.
    }
  )
)
