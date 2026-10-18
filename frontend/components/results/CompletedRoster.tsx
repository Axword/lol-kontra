'use client'
import { useId, useState } from 'react'
import { Daily, DailySlot, GameAnswer, GameState, useDailySolutions } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { roleLabel } from '@/lib/flags'
import { useDialog } from '../ui/useDialog'
import PlayerPortrait from '../roster/PlayerPortrait'
import RarityIndicator from '../roster/RarityIndicator'
import RiftBoard from '../roster/RiftBoard'
import SlotList from '../roster/SlotList'
import LoadError from '@/app/load-error'

type Mode = 'mine' | 'popular' | 'rare' | 'all'

export default function CompletedRoster({ daily, state }: { daily: Daily; state: GameState }) {
  const locale = usePrefs((s) => s.locale)
  const token = usePrefs((s) => s.guestToken)
  const pl = locale === 'pl'
  const [mode, setMode] = useState<Mode>('mine')
  const [inspecting, setInspecting] = useState<DailySlot | null>(null)
  const [query, setQuery] = useState('')
  const data = useDailySolutions(daily.id, token)
  const dialog = useDialog<HTMLDivElement>(!!inspecting, () => setInspecting(null))
  const titleId = useId()
  const actual = Object.fromEntries(state.answers.filter((answer) => answer.is_correct).map((answer) => [answer.daily_slot, answer]))
  const answers: Record<number, GameAnswer> = Object.fromEntries(
    Object.entries(actual).map(([id, answer]) => [id, { ...answer, rarity_percent: null }]),
  )
  // Historical scores stay fixed; popularity reflects the current real votes.
  for (const slot of data.data?.slots || []) {
    const answer = answers[slot.slot_id]
    const player = slot.players.find((candidate) => candidate.id === answer?.player)
    if (answer && player) answers[slot.slot_id] = { ...answer, rarity_percent: player.pick_percent }
  }
  if (mode !== 'mine' && mode !== 'all' && data.data) {
    for (const slot of data.data.slots) {
      const player = slot.players.find((candidate) => candidate.id === data.data![mode][String(slot.slot_id)])
      if (!player) { delete answers[slot.slot_id]; continue }
      answers[slot.slot_id] = { id: -slot.slot_id, daily_slot: slot.slot_id, slot_role: slot.role,
        player: player.id, player_nickname: player.nickname, player_slug: player.slug, is_correct: true,
        rarity_tier: null, rarity_percent: player.pick_percent, points_awarded: -player.pick_percent,
        deduction: player.pick_percent, is_diamond_pick: false }
    }
  }
  const open = (slot: DailySlot) => { setQuery(''); setInspecting(slot) }
  const visible = data.data?.slots.find((slot) => slot.slot_id === inspecting?.id)?.players.filter((player) =>
    player.nickname.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) || []
  const candidateCounts = mode === 'all'
    ? Object.fromEntries((data.data?.slots || []).map((slot) => [slot.slot_id, slot.players.length]))
    : undefined

  return <div className="space-y-4">
    {data.isError && <LoadError onRetry={() => { void data.refetch() }} />}
    <RiftBoard slots={daily.slots} answers={mode === 'all' ? {} : answers} onPick={open} inspect
      candidateCounts={candidateCounts}
      portraits={Object.fromEntries((data.data?.slots || []).flatMap((slot) => slot.players.map((player) => [player.id, player.portrait_url])))} />
    <SlotList slots={daily.slots} answers={mode === 'all' ? {} : answers} onPick={open} inspect candidateCounts={candidateCounts} />
    <div className="flex justify-center">
      <select aria-label={pl ? 'Wyświetlany skład' : 'Displayed roster'} value={mode} onChange={(event) => setMode(event.target.value as Mode)}
        className="border bg-white px-4 py-2 text-sm" style={{ borderColor: 'var(--line)' }}>
        <option value="mine">{pl ? 'Mój skład' : 'My roster'}</option>
        <option value="rare" disabled={!data.data}>{pl ? 'Najrzadszy skład' : 'Rarest roster'}</option>
        <option value="popular" disabled={!data.data}>{pl ? 'Najpopularniejszy skład' : 'Most popular roster'}</option>
        <option value="all" disabled={!data.data}>{pl ? 'Wszystkie odpowiedzi' : 'All answers'}</option>
      </select>
    </div>
    {inspecting && <div className="fixed inset-0 z-50 flex items-end justify-center p-2 sm:items-center sm:p-6">
      <div className="picker-backdrop absolute inset-0" onClick={() => setInspecting(null)} />
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className="panel relative flex max-h-[calc(100dvh-16px)] w-full max-w-lg flex-col sm:max-h-[calc(100dvh-48px)]">
        <div className="shrink-0 border-b px-6 py-5" style={{ borderColor: 'var(--line)' }}>
          <div className="flex items-start justify-between gap-4">
            <h2 id={titleId} className="text-xl font-semibold">{roleLabel(inspecting.role, locale)}</h2>
            <button onClick={() => setInspecting(null)} aria-label={pl ? 'Zamknij' : 'Close'} className="h-8 w-8 text-2xl leading-none">×</button>
          </div>
          <ul className="mt-3 space-y-2 text-sm" style={{ color: 'var(--text-dim)' }}>
            {inspecting.conditions.map((condition) => <li key={condition.id}>{pl ? condition.label_pl : condition.label_en}</li>)}
          </ul>
          <input data-dialog-focus className="field mt-4" value={query} onChange={(event) => setQuery(event.target.value)}
            aria-label={pl ? 'Nick zawodnika' : 'Player nickname'} placeholder={pl ? 'Wpisz nick zawodnika' : 'Type a player nickname'} />
        </div>
        {data.isLoading && <p role="status" className="p-6 text-sm">{pl ? 'Wczytywanie odpowiedzi…' : 'Loading answers…'}</p>}
        {data.isError && <div className="p-4"><LoadError onRetry={() => { void data.refetch() }} /></div>}
        {!!query.trim() && !data.isLoading && !data.isError && visible.length === 0 && <p className="p-6 text-sm">{pl ? 'Brak wyników' : 'No results'}</p>}
        <ul className="min-h-0 overflow-y-auto scroll-thin">
          {visible.map((player) => <li key={player.id} className="flex items-center gap-3 border-b px-6 py-3" style={{ borderColor: 'var(--line-soft)' }}>
            <PlayerPortrait url={player.portrait_url} />
            <span className="min-w-0 flex-1 truncate font-semibold">{player.nickname}</span>
            <RarityIndicator percent={player.pick_percent} locale={locale} className="ml-auto shrink-0 text-right text-xs" />
          </li>)}
        </ul>
      </div>
    </div>}
  </div>
}
