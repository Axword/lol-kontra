'use client'
import { useEffect, useRef, useState } from 'react'
import { GAME_ORIGIN, LEGACY_ORIGIN, migrationCompleteUrl, readStoredProfile, safeMigrationPath } from '@/lib/domain-migration'
import { usePrefs } from '@/lib/store'

export default function LegacyBridge({ next: destination }: { next?: string }) {
  const pl = usePrefs(state => state.locale) === 'pl'
  const started = useRef(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const next = safeMigrationPath(destination)
    if (window.location.origin !== LEGACY_ORIGIN) { window.location.replace(GAME_ORIGIN + next); return }
    try {
      const token = readStoredProfile(window.localStorage)
      if (!token) { window.location.replace(migrationCompleteUrl(next)); return }
      const form = document.createElement('form')
      form.method = 'POST'
      form.action = `${GAME_ORIGIN}/profile-transfer`
      for (const [name, value] of [['guest_token', token], ['next', next]]) {
        const input = document.createElement('input')
        input.type = 'hidden'; input.name = name; input.value = value
        form.appendChild(input)
      }
      document.body.appendChild(form)
      form.submit()
    } catch { setFailed(true) }
  }, [destination])
  return <main className="mx-auto max-w-lg space-y-5 px-6 py-20">
    <h1 className="text-3xl font-semibold">WORLDS KONTRA</h1>
    <p role={failed ? 'alert' : 'status'}>{failed
      ? (pl ? 'Nie udało się odczytać dostępu do profilu. Dane starej strony nie zostały zmienione.' : 'Could not read your profile access. Your data on the old site has not changed.')
      : (pl ? 'Przenosimy Twój profil na nowy adres…' : 'Moving your profile to the new address…')}</p>
    <a href={GAME_ORIGIN} className="inline-block underline underline-offset-4">{pl ? 'Przejdź do gry' : 'Open the game'}</a>
  </main>
}
