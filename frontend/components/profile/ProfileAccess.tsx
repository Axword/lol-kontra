'use client'
import { ChangeEvent, useEffect, useId, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { GuestProfile } from '@/lib/guest-profile'
import { usePrefs } from '@/lib/store'
import { downloadProfileAccess, MAX_PROFILE_FILE_BYTES, readProfileAccessFile } from '@/lib/profile-access'
import { activateProfile } from '@/lib/activate-profile'
import { LEGACY_ORIGIN } from '@/lib/domain-migration'

export default function ProfileAccess({ guestToken, onRestored }: { guestToken: string; onRestored: () => void }) {
  const pl = usePrefs(s => s.locale) === 'pl'
  const client = useQueryClient()
  const inputId = useId()
  const request = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const mounted = useRef(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [saved, setSaved] = useState(false)
  const [restored, setRestored] = useState(false)
  const [preview, setPreview] = useState<{ token: string; current: string; profile: GuestProfile } | null>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; request.current?.abort() } }, [])
  useEffect(() => { sequence.current += 1; request.current?.abort(); setPreview(null); setBusy(false) }, [guestToken])

  const save = () => {
    try { downloadProfileAccess(guestToken); setSaved(true); setError(false) } catch { setError(true) }
  }
  const load = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const id = ++sequence.current
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    setPreview(null); setError(false); setRestored(false); setBusy(true)
    try {
      if (file.size > MAX_PROFILE_FILE_BYTES) throw new Error('invalid_profile_file')
      const token = readProfileAccessFile(await file.text())
      if (controller.signal.aborted) return
      const { data } = await api.post<GuestProfile>('/guest/profile/preview/', { guest_token: token }, { signal: controller.signal })
      if (!mounted.current || id !== sequence.current) return
      if (typeof data.display_name !== 'string' || typeof data.stats?.games_played !== 'number') throw new Error('invalid_profile_response')
      setPreview({ token, current: guestToken, profile: data })
    } catch { if (mounted.current && id === sequence.current && !controller.signal.aborted) setError(true) }
    finally { if (mounted.current && id === sequence.current) setBusy(false) }
  }
  const activate = async () => {
    if (!preview || busy) return
    setBusy(true)
    try {
      await activateProfile(client, preview.current, preview.token, preview.profile)
      onRestored()
      setPreview(null); setRestored(true); setError(false)
    } catch { if (mounted.current) setError(true) }
    finally { if (mounted.current) setBusy(false) }
  }
  return <section className="space-y-3 border-t pt-5" aria-labelledby={`${inputId}-title`} style={{ borderColor: 'var(--line)' }}>
    <h2 id={`${inputId}-title`} className="text-sm font-semibold">{pl ? 'Dostęp do profilu' : 'Profile access'}</h2>
    <p className="text-xs leading-relaxed" style={{ color: 'var(--text-dim)' }}>
      {pl ? 'Zapisz plik, aby otworzyć ten sam profil na nowej domenie lub innym urządzeniu. Plik daje dostęp do profilu — zachowaj go dla siebie.'
        : 'Save a file to open the same profile on a new domain or another device. This file grants access to your profile — keep it private.'}
    </p>
    <div className="flex flex-wrap gap-2">
      <button type="button" onClick={save} disabled={!guestToken || busy} className="min-h-11 border px-4 text-sm font-semibold disabled:opacity-50" style={{ borderColor: 'var(--line)' }}>{pl ? 'Zapisz dostęp do profilu' : 'Save profile access'}</button>
      <label htmlFor={inputId} className="flex min-h-11 cursor-pointer items-center border px-4 text-sm font-semibold" style={{ borderColor: 'var(--line)', opacity: busy ? .5 : 1 }}>{pl ? 'Wczytaj dostęp do profilu' : 'Load profile access'}</label>
      <input id={inputId} type="file" accept=".json,application/json" disabled={busy} onChange={event => { void load(event) }} className="sr-only" />
    </div>
    <a href={`${LEGACY_ORIGIN}/legacy-migration?next=%2Fprofile`} className="inline-block text-xs underline underline-offset-4">
      {pl ? 'Przenieś profil ze starej domeny' : 'Recover profile from the old domain'}
    </a>
    {busy && <p role="status" className="text-xs">{pl ? 'Sprawdzanie profilu…' : 'Checking profile…'}</p>}
    {saved && !preview && !restored && <p role="status" className="text-xs">{pl ? 'Plik dostępu został pobrany.' : 'Profile access file downloaded.'}</p>}
    {error && <p role="alert" className="text-xs" style={{ color: 'var(--bad)' }}>{pl ? 'Nie udało się wczytać profilu. Sprawdź plik i czy dane zostały już przeniesione na tę domenę. Bieżący profil nie został zmieniony.' : 'Could not load the profile. Check the file and that its data has been migrated to this domain. Your current profile has not changed.'}</p>}
    {preview && <div className="space-y-3 border p-4" style={{ borderColor: 'var(--line)' }}>
      <p className="text-sm font-semibold">{preview.profile.display_name} · {preview.profile.stats.games_played} {pl ? 'rozegranych gier' : 'games played'}</p>
      <p className="text-xs" style={{ color: 'var(--text-dim)' }}>{pl ? 'To przełączy profil w tej przeglądarce. Jeśli używasz tu innego profilu, najpierw zapisz jego plik. Profile nie są łączone.' : 'This switches the profile used in this browser. Save your current profile first if needed. Profiles are not merged.'}</p>
      <div className="flex gap-3">
        <button type="button" disabled={busy} onClick={() => { void activate() }} className="btn btn-gold">{pl ? 'Użyj tego profilu' : 'Use this profile'}</button>
        <button type="button" disabled={busy} onClick={() => setPreview(null)} className="text-sm underline">{pl ? 'Anuluj' : 'Cancel'}</button>
      </div>
    </div>}
    {restored && <p role="status" className="text-xs">{pl ? 'Profil wczytany. Wyniki i zapisane składy są dostępne.' : 'Profile loaded. Your results and saved rosters are available.'}</p>}
  </section>
}
