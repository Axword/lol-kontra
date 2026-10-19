'use client'
import { FormEvent, useState } from 'react'
import { usePrefs } from '@/lib/store'
import { formatApiError } from '@/lib/errors'
import { useGuestProfile, useGuestToken, useUpdateGuestNickname } from '@/lib/guest-profile'

export default function FinalNicknamePrompt({ eligible = true }: { eligible?: boolean }) {
  const pl = usePrefs((state) => state.locale) === 'pl'
  const token = useGuestToken()
  const profile = useGuestProfile(token)
  const update = useUpdateGuestNickname()
  const [nickname, setNickname] = useState('')
  if (!eligible || !profile.data || profile.data.nickname || profile.data.has_custom_nickname) return null

  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token || !nickname.trim() || update.isPending) return
    update.mutate({ guest_token: token, nickname })
  }
  return <form onSubmit={save} className="mt-6 space-y-2 border-t pt-5" style={{ borderColor: 'var(--line)' }}>
    <label htmlFor="result-nickname" className="block text-sm font-semibold">{pl ? 'Zapisz jako…' : 'Save as…'}</label>
    <div className="flex flex-wrap gap-2">
      <input id="result-nickname" autoComplete="nickname" name="nickname" className="field min-w-0 flex-1"
        value={nickname} placeholder={profile.data.display_name} disabled={update.isPending}
        aria-invalid={update.isError || undefined} aria-describedby={update.isError ? 'result-nickname-error' : undefined}
        onChange={(event) => { setNickname(event.target.value); update.reset() }} />
      <button type="submit" disabled={!token || !nickname.trim() || update.isPending} className="btn btn-gold disabled:opacity-50">
        {update.isPending ? (pl ? 'Zapisywanie…' : 'Saving…') : (pl ? 'Zapisz nick' : 'Save nickname')}
      </button>
    </div>
    {update.isError && <p id="result-nickname-error" role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>
      {formatApiError(update.error, pl ? 'Nie udało się zapisać nicku.' : 'Could not save your nickname.')}
    </p>}
  </form>
}
