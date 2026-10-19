'use client'
import { FormEvent, useState } from 'react'
import { usePrefs } from '@/lib/store'
import { formatApiError } from '@/lib/errors'
import { useGuestProfile, useGuestToken, useUpdateGuestNickname } from '@/lib/guest-profile'
import GameLayout from '@/components/layout/GameLayout'
import ProfileStatistics from '@/components/profile/ProfileStatistics'

export default function ProfilePage() {
  const locale = usePrefs((s) => s.locale)
  const pl = locale === 'pl'
  const guestToken = useGuestToken()
  const profile = useGuestProfile(guestToken)
  const update = useUpdateGuestNickname()
  const [draft, setDraft] = useState<string | null>(null)
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
                ? <p role="alert" style={{ color: 'var(--bad)' }}>{formatApiError(update.error, pl ? 'Nie udało się zapisać nicku. Spróbuj ponownie.' : 'Could not save your nickname. Try again.')}</p>
                : update.isSuccess && draft === null
                ? <p role="status">{pl ? 'Nick zapisany.' : 'Nickname saved.'}</p>
                : <p>{pl ? 'Zostaw puste, aby wrócić do domyślnego nicku.' : 'Leave blank to restore your default nickname.'}</p>}
            </div>
          </form>

          <p className="text-[15px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {pl
              ? 'Grasz jako gość. Twoje wyniki są przypisane do tej przeglądarki – wyczyszczenie danych strony je usunie.'
              : 'You are playing as a guest. Your results are tied to this browser and will be lost if you clear site data.'}
          </p>

          {profile.isLoading && <p role="status" className="text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Wczytywanie profilu…' : 'Loading profile…'}</p>}
          {profile.isError && <div role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>
            <p>{formatApiError(profile.error, pl ? 'Nie udało się wczytać profilu.' : 'Could not load your profile.')}</p>
            <button type="button" onClick={() => { void profile.refetch() }} className="mt-2 underline">{pl ? 'Spróbuj ponownie' : 'Try again'}</button>
          </div>}
          {profile.data && <ProfileStatistics stats={profile.data.stats} />}
        </div>
      </div>
    </GameLayout>
  )
}
