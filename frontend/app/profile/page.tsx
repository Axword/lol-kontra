'use client'
import { usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'

export default function ProfilePage() {
  const locale = usePrefs((s) => s.locale)
  const pl = locale === 'pl'

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header>
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{pl ? 'Profil' : 'Profile'}</h1>
        </header>

        <div className="max-w-2xl border bg-white p-6 sm:p-8" style={{ borderColor: 'var(--line)' }}>
          <p className="text-[15px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {pl
              ? 'Grasz jako gość. Twoje wyniki są przypisane do tej przeglądarki – wyczyszczenie danych strony je usunie.'
              : 'You are playing as a guest. Your results are tied to this browser and will be lost if you clear site data.'}
          </p>
        </div>

        {/*
          Świadomie nie pokazujemy tu kart ze statystykami. Do czasu uruchomienia
          logowania nie mamy czym ich wypełnić, a puste liczniki („0”, „—”)
          sprawiały wrażenie zepsutej strony.
        */}
      </div>
    </GameLayout>
  )
}
