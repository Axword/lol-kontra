'use client'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import type { DailySlot, GameAnswer, Player } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { useGuestToken } from '@/lib/guest-profile'
import { useInfinity, useInfinityAnswer, useStartInfinity } from '@/lib/infinity'
import { sound } from '@/lib/sound'
import GameLayout from '@/components/layout/GameLayout'
import RiftBoard from '@/components/roster/RiftBoard'
import SlotList from '@/components/roster/SlotList'
import PlayerPickerModal from '@/components/roster/PlayerPickerModal'
import LoadError from '@/app/load-error'

export default function InfinityPage() {
  const pl = usePrefs(s => s.locale) === 'pl'
  const token = useGuestToken()
  const query = useInfinity(token)
  const start = useStartInfinity(token)
  const answer = useInfinityAnswer(token)
  const run = query.data?.run
  const [slot, setSlot] = useState<DailySlot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const pending = useRef(false)
  const answers = Object.fromEntries((run?.answers || []).map(a => [a.daily_slot,a])) as Record<number, GameAnswer>
  useEffect(() => {setSlot(null);setError(null)}, [run?.board_id,run?.is_over])
  useEffect(() => {
    if (slot && answers[slot.id]?.is_correct) setSlot(null)
  }, [run?.answers, slot]) // eslint-disable-line react-hooks/exhaustive-deps

  const choose = (next:DailySlot) => {
    if (pending.current || run?.is_over || answers[next.id]?.is_correct) return
    setError(null);setFeedback(null);setSlot(next);sound.open()
  }
  const select = (player:Player) => {
    if (!run || !slot || pending.current || run.is_over) return
    pending.current = true
    setError(null)
    answer.mutate({run_id:run.id,board_id:run.board_id,position:slot.position,player_slug:player.slug}, {
      onSuccess: data => {
        if (data.correct) {
          sound.success();setSlot(null)
          setFeedback(pl ? `${data.player_nickname} pasuje.` : `${data.player_nickname} fits.`)
        } else {
          sound.error()
          setError(pl ? `${data.player_nickname} nie spełnia warunków. Pozostało żyć: ${data.run?.errors_left}.`
            : `${data.player_nickname} does not match. Lives left: ${data.run?.errors_left}.`)
        }
      },
      onError: () => setError(pl ? 'Nie udało się sprawdzić odpowiedzi. Odświeżono stan serii — spróbuj ponownie.' : 'Could not check the answer. Your run has been refreshed — try again.'),
      onSettled: () => {pending.current=false},
    })
  }
  return <GameLayout gameMode="infinity"><div className="mx-auto max-w-[1000px] space-y-5">
    <header className="flex flex-wrap items-baseline justify-between gap-3">
      <h1 className="text-[28px] font-bold tracking-tight sm:text-[34px]">Infinity</h1>
      <Link href="/infinity/leaderboard" className="text-sm underline underline-offset-4" style={{color:'var(--gold)'}}>{pl ? 'Ranking Infinity' : 'Infinity leaderboard'}</Link>
    </header>
    <p className="max-w-2xl text-sm leading-relaxed" style={{color:'var(--text-dim)'}}>{pl
      ? 'Ukończ piątkę, aby wylosować kolejną planszę. Masz łącznie 10 pomyłek na całą serię. Ranking liczy trafionych zawodników w Twojej najlepszej serii.'
      : 'Complete all five positions to draw another board. You have 10 mistakes for the entire run. The leaderboard counts players guessed in your best run.'}</p>
    {!token || query.isLoading ? <p role="status">{pl ? 'Wczytywanie…' : 'Loading…'}</p>
      : query.isError ? <LoadError onRetry={() => {void query.refetch()}} />
      : <>
        {run && <dl className="flex flex-wrap justify-between gap-4 border bg-white px-4 py-3" style={{borderColor:'var(--line)'}}>
          <div><dt className="text-xs" style={{color:'var(--text-faint)'}}>{pl ? 'Trafienia' : 'Correct guesses'}</dt><dd className="mt-1 text-2xl font-semibold tabular" style={{color:'var(--gold)'}}>{run.correct_count}</dd></div>
          <div><dt className="text-xs" style={{color:'var(--text-faint)'}}>{pl ? 'Rekord' : 'Personal best'}</dt><dd className="mt-1 text-2xl font-semibold tabular">{query.data?.personal_best ?? 0}</dd></div>
          <div><dt className="text-xs" style={{color:'var(--text-faint)'}}>{pl ? 'Życia' : 'Lives'}</dt><dd className="mt-1 text-2xl font-semibold tabular" style={{color:run.is_over?'var(--bad)':undefined}}>{run.errors_left} / {run.max_errors}</dd></div>
        </dl>}
        {(!run || run.is_over) && <div className="space-y-4 border bg-white p-6" style={{borderColor:'var(--line)'}}>
          {run?.is_over && <h2 className="text-xl font-semibold">{pl ? 'Seria zakończona' : 'Run finished'}</h2>}
          <button disabled={start.isPending} onClick={() => {setFeedback(null);start.mutate()}} className="btn btn-gold disabled:opacity-50">
            {start.isPending ? (pl?'Losowanie…':'Drawing…') : run ? (pl?'Zagraj ponownie':'Play again') : (pl?'Graj w Infinity':'Play Infinity')}</button>
          {start.isError && <p role="alert" className="text-sm" style={{color:'var(--bad)'}}>{pl?'Nie udało się rozpocząć serii. Spróbuj ponownie.':'Could not start a run. Try again.'}</p>}
        </div>}
        {run && <>
          <RiftBoard key={run.board_id} slots={run.slots} answers={answers} onPick={choose} disabled={run.is_over} activeSlotId={slot?.id} showRarity={false} />
          <SlotList slots={run.slots} answers={answers} onPick={choose} disabled={run.is_over} showRarity={false} />
        </>}
      </>}
    {feedback && <p role="status" className="text-sm" style={{color:'var(--gold)'}}>{feedback}</p>}
    <PlayerPickerModal slot={slot} open={!!slot} busy={answer.isPending} error={error}
      onClose={() => {if(!pending.current){setSlot(null);setError(null);sound.close()}}} onSelect={select} />
  </div></GameLayout>
}
