'use client'
import { FormEvent, ReactNode, RefObject, useId, useRef, useState } from 'react'
import { Check, Shield, X } from 'lucide-react'
import { usePrefs } from '@/lib/store'
import { formatApiError } from '@/lib/errors'
import {
  GuestProfile, SupportedTeam, useGuestProfile, useGuestToken,
  useUpdateGuestNickname, useUpdateSupportedTeam, useWorldsTeams,
} from '@/lib/guest-profile'
import { useDialog } from '@/components/ui/useDialog'

function IdentityDialog({ title, onClose, returnFocusRef, children, wide = false }: {
  title: string; onClose: () => void; returnFocusRef: RefObject<HTMLElement>; children: ReactNode; wide?: boolean
}) {
  const pl = usePrefs((state) => state.locale) === 'pl'
  const titleId = useId()
  const dialogRef = useDialog<HTMLDivElement>(true, onClose, returnFocusRef)
  return <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
    <div className="absolute inset-0" style={{ background: 'rgba(24,36,28,.35)' }} onClick={onClose} />
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
      className={`relative flex max-h-[calc(100dvh-32px)] w-full flex-col border bg-[var(--panel)] ${wide ? 'max-w-xl' : 'max-w-sm'}`}
      style={{ borderColor: 'var(--line)' }}>
      <div className="flex items-center justify-between gap-4 border-b px-5 py-4" style={{ borderColor: 'var(--line)' }}>
        <h2 id={titleId} className="text-xl font-semibold">{title}</h2>
        <button type="button" onClick={onClose} aria-label={pl ? 'Zamknij' : 'Close'}
          className="flex h-9 w-9 shrink-0 items-center justify-center border hover:bg-[var(--panel-2)]" style={{ borderColor: 'var(--line)' }}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>
      {children}
    </div>
  </div>
}

function NicknameDialog({ guestToken, profile, onClose, returnFocusRef }: {
  guestToken: string; profile?: GuestProfile; onClose: () => void; returnFocusRef: RefObject<HTMLElement>
}) {
  const pl = usePrefs((state) => state.locale) === 'pl'
  const update = useUpdateGuestNickname()
  const [draft, setDraft] = useState<string | null>(null)
  const inputId = useId()
  const feedbackId = useId()
  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!guestToken || update.isPending) return
    update.mutate({ guest_token: guestToken, nickname: draft ?? profile?.nickname ?? '' }, { onSuccess: onClose })
  }
  return <IdentityDialog title={pl ? 'Zmień nick' : 'Change nickname'} onClose={onClose} returnFocusRef={returnFocusRef}>
    <form onSubmit={save} className="space-y-4 p-5">
      <label htmlFor={inputId} className="block text-sm font-semibold">{pl ? 'Nick' : 'Nickname'}</label>
      <input id={inputId} name="nickname" autoComplete="nickname" data-dialog-focus className="field w-full"
        value={draft ?? profile?.nickname ?? ''} aria-invalid={update.isError || undefined} aria-describedby={feedbackId}
        disabled={update.isPending}
        onChange={(event) => { setDraft(event.target.value); update.reset() }} />
      <div id={feedbackId}>
        {update.isError && <p role="alert" className="text-sm" style={{ color: 'var(--bad)' }}>
          {formatApiError(update.error, pl ? 'Nie udało się zapisać nicku. Spróbuj ponownie.' : 'Could not save your nickname. Try again.', pl ? 'pl' : 'en')}
        </p>}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="min-h-10 border px-4 text-sm" style={{ borderColor: 'var(--line)' }}>{pl ? 'Anuluj' : 'Cancel'}</button>
        <button type="submit" disabled={!guestToken || update.isPending} className="min-h-10 border px-4 text-sm font-semibold disabled:opacity-50"
          style={{ borderColor: 'var(--gold)', background: 'var(--gold)', color: 'var(--panel)' }}>
          {update.isPending ? (pl ? 'Zapisywanie…' : 'Saving…') : (pl ? 'Zapisz' : 'Save')}
        </button>
      </div>
    </form>
  </IdentityDialog>
}

export function TeamLogo({ team, small = false }: { team: SupportedTeam; small?: boolean }) {
  const [failed, setFailed] = useState(false)
  const dark = ['dk', 'g2', 'hle', 'tlaw', 'tsw'].includes(team.id)
  if (failed) return <Shield size={small ? 18 : 28} strokeWidth={1.5} aria-hidden="true" />
  // The adjacent team name labels the decorative logo.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={team.logo_url} alt="" width={small ? 22 : 36} height={small ? 22 : 36}
    className={`${small ? 'h-[22px] w-[22px]' : 'h-9 w-9'} shrink-0 object-contain p-1`}
    style={{ background: dark ? '#26312d' : '#f1f4f1' }} onError={() => setFailed(true)} />
}

export function TeamDialog({ guestToken, team, onClose, returnFocusRef }: {
  guestToken: string; team?: SupportedTeam | null; onClose: () => void; returnFocusRef: RefObject<HTMLElement>
}) {
  const pl = usePrefs((state) => state.locale) === 'pl'
  const teams = useWorldsTeams()
  const update = useUpdateSupportedTeam()
  const selectTeam = (id: string | null) => {
    if (!guestToken || update.isPending) return
    update.mutate({ guest_token: guestToken, supported_team: id }, { onSuccess: onClose })
  }
  return <IdentityDialog title={pl ? 'Kibicuję' : 'I support'} onClose={onClose} returnFocusRef={returnFocusRef} wide>
    <div className="min-h-0 overflow-y-auto p-5 scroll-thin">
      {teams.isLoading && <p role="status" className="py-4 text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Wczytywanie drużyn…' : 'Loading teams…'}</p>}
      {teams.isError && <div role="alert" className="space-y-2 text-sm" style={{ color: 'var(--bad)' }}>
        <p>{formatApiError(teams.error, pl ? 'Nie udało się wczytać drużyn.' : 'Could not load teams.', pl ? 'pl' : 'en')}</p>
        <button type="button" className="underline" onClick={() => { void teams.refetch() }}>{pl ? 'Spróbuj ponownie' : 'Try again'}</button>
      </div>}
      {teams.data && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {teams.data.teams.map((option) => <button key={option.id} type="button" disabled={update.isPending || !guestToken}
          aria-pressed={team?.id === option.id} onClick={() => selectTeam(option.id)}
          className="flex min-h-[68px] items-center gap-3 border p-3 text-left hover:bg-[var(--panel-2)] disabled:opacity-50"
          style={{ borderColor: team?.id === option.id ? 'var(--gold)' : 'var(--line)' }}>
          <TeamLogo team={option} />
          <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">{option.name}</span>
            <span className="block text-xs" style={{ color: 'var(--text-faint)' }}>{option.code} · {option.region}</span></span>
          {team?.id === option.id && <Check size={16} aria-hidden="true" style={{ color: 'var(--gold)' }} />}
        </button>)}
      </div>}
      {update.isPending && <p role="status" className="mt-4 text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Zapisywanie…' : 'Saving…'}</p>}
      {update.isError && <p role="alert" className="mt-4 text-sm" style={{ color: 'var(--bad)' }}>
        {formatApiError(update.error, pl ? 'Nie udało się zapisać drużyny. Spróbuj ponownie.' : 'Could not save your team. Try again.', pl ? 'pl' : 'en')}
      </p>}
    </div>
    <div className="flex shrink-0 justify-end border-t px-5 py-4" style={{ borderColor: 'var(--line)' }}>
      <button type="button" disabled={!team || update.isPending || !guestToken} onClick={() => selectTeam(null)}
        className="min-h-10 border px-4 text-sm disabled:opacity-40" style={{ borderColor: 'var(--line)' }}>
        {pl ? 'Bez drużyny' : 'No team'}
      </button>
    </div>
  </IdentityDialog>
}

export default function GuestIdentity() {
  const pl = usePrefs((state) => state.locale) === 'pl'
  const guestToken = useGuestToken()
  const profile = useGuestProfile(guestToken)
  const [editor, setEditor] = useState<'nickname' | 'team' | null>(null)
  const nicknameButton = useRef<HTMLButtonElement>(null)
  const teamButton = useRef<HTMLButtonElement>(null)
  const name = profile.data?.nickname || profile.data?.display_name.replace(/^(Gość|Guest)-/u, '') || '—'
  const team = profile.data?.supported_team
  return <div className="flex min-w-0 items-center gap-1">
    <button type="button" ref={nicknameButton} disabled={!guestToken} onClick={() => setEditor('nickname')}
      aria-label={`${pl ? 'Zmień nick' : 'Change nickname'}: ${name}`} title={`${pl ? 'NICK' : 'NAME'}: ${name}`}
      className="min-h-9 min-w-0 max-w-[90px] truncate px-1 text-[11px] font-medium sm:max-w-[160px]"
      style={{ color: 'var(--text-dim)' }}>{pl ? 'NICK' : 'NAME'}: {name}</button>
    <button type="button" ref={teamButton} disabled={!guestToken} onClick={() => setEditor('team')}
      aria-label={team ? `${pl ? 'Kibicuję' : 'I support'}: ${team.name}` : (pl ? 'Wybierz drużynę' : 'Choose a team')}
      title={team?.name || (pl ? 'Wybierz drużynę' : 'Choose a team')}
      className="flex h-9 w-8 shrink-0 items-center justify-center hover:bg-[var(--panel-2)]" style={{ color: 'var(--text-dim)' }}>
      {team ? <TeamLogo key={team.id} team={team} small /> : <Shield size={18} strokeWidth={1.7} aria-hidden="true" />}
    </button>
    {editor === 'nickname' && <NicknameDialog guestToken={guestToken} profile={profile.data}
      onClose={() => setEditor((current) => current === 'nickname' ? null : current)} returnFocusRef={nicknameButton} />}
    {editor === 'team' && <TeamDialog guestToken={guestToken} team={team}
      onClose={() => setEditor((current) => current === 'team' ? null : current)} returnFocusRef={teamButton} />}
  </div>
}
