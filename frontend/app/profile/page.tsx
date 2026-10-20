'use client'
import { FormEvent, useRef, useState } from 'react'
import { Shield } from 'lucide-react'
import { usePrefs } from '@/lib/store'
import { formatApiError } from '@/lib/errors'
import { useGuestProfile, useGuestToken, useUpdateGuestNickname } from '@/lib/guest-profile'
import GameLayout from '@/components/layout/GameLayout'
import ProfileStatistics from '@/components/profile/ProfileStatistics'
import ProfileAccess from '@/components/profile/ProfileAccess'
import { TeamDialog, TeamLogo } from '@/components/layout/GuestIdentity'

export default function ProfilePage() {
  const locale = usePrefs((s) => s.locale)
  const pl = locale === 'pl'
  const guestToken = useGuestToken()
  const profile = useGuestProfile(guestToken)
  const update = useUpdateGuestNickname()
  const [draft, setDraft] = useState<string | null>(null)
  const [teamOpen, setTeamOpen] = useState(false)
  const teamButton = useRef<HTMLButtonElement>(null)
  const team = profile.data?.supported_team
  const nickname = draft ?? profile.data?.nickname ?? ''

  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!guestToken || update.isPending) return
    const submitted = nickname
    update.mutate({ guest_token: guestToken, nickname: submitted }, {
      onSuccess: () => { setDraft((current) => current === submitted ? null : current) },
    })
  }

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header>
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{pl ? 'Profil' : 'Profile'}</h1>
        </header>

        <div className="max-w-2xl space-y-6 border bg-white p-6 sm:p-8" style={{ borderColor: 'var(--line)' }}>
          <form onSubmit={save} className="space-y-3">
            <label htmlFor="guest-nickname" className="block text-sm font-semibold">{pl ? 'Nick' : 'Nickname'}</label>
            <div className="flex flex-wrap items-start gap-2">
              <input id="guest-nickname" name="nickname" autoComplete="nickname" className="field min-w-0 flex-1"
                value={nickname} aria-invalid={update.isError || undefined} aria-describedby="guest-nickname-feedback"
                onChange={(event) => { setDraft(event.target.value); if (!update.isPending) update.reset() }} />
              <button type="submit" disabled={!guestToken || update.isPending}
                className="min-h-11 border px-5 text-sm font-semibold disabled:opacity-50"
                style={{ borderColor: 'var(--gold)', background: 'var(--gold)', color: '#fff' }}>
                {update.isPending ? (pl ? 'Zapisywanie…' : 'Saving…') : (pl ? 'Zapisz' : 'Save')}
              </button>
            </div>
            <div id="guest-nickname-feedback" className="text-xs" style={{ color: 'var(--text-faint)' }}>
              {update.isError
                ? <p role="alert" style={{ color: 'var(--bad)' }}>{formatApiError(update.error, pl ? 'Nie udało się zapisać nicku. Spróbuj ponownie.' : 'Could not save your nickname. Try again.', locale)}</p>
                : update.isSuccess && draft === null
                ? <p role="status">{pl ? 'Nick zapisany.' : 'Nickname saved.'}</p>
                : <p>{pl ? 'Zostaw puste, aby wrócić do domyślnego nicku.' : 'Leave blank to restore your default nickname.'}</p>}
            </div>
          </form>

          <section aria-labelledby="profile-badge-title" className="space-y-3">
            <h2 id="profile-badge-title" className="text-sm font-semibold">{pl ? 'Odznaka' : 'Badge'}</h2>
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex min-h-11 items-center gap-2 text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
                {team ? <><TeamLogo key={team.id} team={team} /><span>{team.name}</span></> : <Shield size={24} strokeWidth={1.7} aria-hidden="true" />}
              </span>
              <button type="button" ref={teamButton} disabled={!guestToken || !profile.data} onClick={() => setTeamOpen(true)} aria-haspopup="dialog"
                className="min-h-11 border px-5 text-sm font-semibold disabled:opacity-50" style={{ borderColor: 'var(--line)' }}>
                {team ? (pl ? 'Zmień drużynę' : 'Change team') : (pl ? 'Wybierz drużynę' : 'Choose a team')}
              </button>
            </div>
            {teamOpen && <TeamDialog guestToken={guestToken} team={team} onClose={() => setTeamOpen(false)} returnFocusRef={teamButton} />}
          </section>

          <p className="text-[15px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {pl
              ? 'Grasz jako gość. Wyniki są zapisane na serwerze, a dostęp do nich jest przypisany do tej przeglądarki. Zapisz plik dostępu przed zmianą domeny lub wyczyszczeniem danych strony.'
              : 'You are playing as a guest. Results are stored on the server; access is tied to this browser. Save your access file before changing domains or clearing site data.'}
          </p>

          <ProfileAccess guestToken={guestToken} onRestored={() => { setDraft(null); update.reset() }} />

          {profile.isLoading && <p role="status" className="text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Wczytywanie profilu…' : 'Loading profile…'}</p>}
          {profile.isError && <div role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>
            <p>{formatApiError(profile.error, pl ? 'Nie udało się wczytać profilu.' : 'Could not load your profile.', locale)}</p>
            <button type="button" onClick={() => { void profile.refetch() }} className="mt-2 underline">{pl ? 'Spróbuj ponownie' : 'Try again'}</button>
          </div>}
          {profile.data && <ProfileStatistics stats={profile.data.stats} />}
        </div>
      </div>
    </GameLayout>
  )
}
