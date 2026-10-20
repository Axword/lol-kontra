'use client'
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { GuestProfile } from '@/lib/guest-profile'
import { usePrefs } from '@/lib/store'
import { activateProfile } from '@/lib/activate-profile'
import { downloadProfileAccess } from '@/lib/profile-access'
import { LEGACY_ORIGIN, migrationCompleteUrl, parseMigrationSession, type MigrationSession } from '@/lib/domain-migration'
import { guestDisplayName } from '@/lib/locale'

type Preview = MigrationSession & { current: string; profile: GuestProfile }
export default function ProfileMigration() {
  const locale = usePrefs(state => state.locale)
  const pl = locale === 'pl'
  const client = useQueryClient()
  const request = useRef<Promise<Preview> | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(true)
  const move = async (data: Preview) => {
    await activateProfile(client, data.current, data.guestToken, data.profile)
    window.location.replace(migrationCompleteUrl(data.next))
  }
  useEffect(() => {
    let cancelled = false
    if (!request.current) request.current = (async () => {
      await usePrefs.persist.rehydrate()
      const current = usePrefs.getState().guestToken
      const response = await fetch('/profile-transfer/session', { method: 'POST', credentials: 'same-origin', cache: 'no-store' })
      if (!response.ok) throw new Error('migration_expired')
      const session = parseMigrationSession(await response.json())
      const { data } = await api.post<GuestProfile>('/guest/profile/preview/', { guest_token: session.guestToken })
      if (typeof data.display_name !== 'string' || typeof data.stats?.games_played !== 'number') throw new Error('invalid_profile')
      return { ...session, current, profile: data }
    })()
    void request.current.then(async data => {
      if (cancelled) return
      if (!data.current || data.current === data.guestToken) { await move(data); return }
      setPreview(data); setBusy(false)
    }).catch(() => { if (!cancelled) { setError(true); setBusy(false) } })
    return () => { cancelled = true }
    // One consumed handoff per page, including React's development remount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client])
  const accept = async () => {
    if (!preview || busy) return
    setBusy(true); setError(false)
    try { await move(preview) } catch { setError(true); setBusy(false) }
  }
  return <main className="mx-auto max-w-lg space-y-5 px-6 py-20">
    <h1 className="text-3xl font-semibold">{pl ? 'Twój profil WORLDS KONTRA' : 'Your WORLDS KONTRA profile'}</h1>
    {busy && <p role="status">{pl ? 'Przywracanie profilu…' : 'Restoring your profile…'}</p>}
    {error && <p role="alert">{pl ? 'Nie udało się przenieść profilu. Bieżący dostęp i stare wyniki nie zostały zmienione.' : 'Could not transfer your profile. Your current access and previous results have not changed.'}</p>}
    {preview && <>
      <p className="text-lg font-semibold">{guestDisplayName(preview.profile.display_name, locale)} · {preview.profile.stats.games_played} {pl ? 'rozegranych gier' : 'games played'}</p>
      <p className="text-sm">{pl ? 'Na nowej domenie używasz innego profilu. Możesz wrócić do swojego poprzedniego profilu.' : 'You are using a different profile on the new domain. You can return to your previous profile.'}</p>
      <div className="flex flex-wrap gap-3">
        <button disabled={busy} onClick={() => { void accept() }} className="btn btn-gold">{pl ? 'Przenieś mój profil' : 'Transfer my profile'}</button>
        <button disabled={busy} onClick={() => window.location.replace(migrationCompleteUrl(preview.next))} className="border px-4 py-2 text-sm">{pl ? 'Zachowaj bieżący profil' : 'Keep my current profile'}</button>
      </div>
      <button disabled={busy} onClick={() => { try { downloadProfileAccess(preview.current) } catch { setError(true) } }} className="text-sm underline underline-offset-4">{pl ? 'Zapisz dostęp do bieżącego profilu' : 'Save access to my current profile'}</button>
    </>}
    {error && <a href={`${LEGACY_ORIGIN}/legacy-migration?next=%2Fprofile`} className="inline-block underline underline-offset-4">{pl ? 'Spróbuj ponownie ze starej strony' : 'Try again from the old site'}</a>}
  </main>
}
