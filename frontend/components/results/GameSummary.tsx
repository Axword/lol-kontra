'use client'
import Link from 'next/link'
import { useId, useRef, useState } from 'react'
import { Daily, GameState } from '@/lib/api'
import CompletedRoster from './CompletedRoster'
import { usePrefs } from '@/lib/store'
import ScoreDistribution from './ScoreDistribution'
import { useDialog } from '../ui/useDialog'
import FinalNicknamePrompt from './FinalNicknamePrompt'

export default function GameSummary({ daily, state }: { daily: Daily; state: GameState }) {
  const locale = usePrefs((s) => s.locale)
  const pl = locale === 'pl'
  const [open, setOpen] = useState(true)
  const titleId = useId()
  const resultButtonRef = useRef<HTMLButtonElement>(null)
  const dialog = useDialog<HTMLDivElement>(open, () => setOpen(false), resultButtonRef)

  return <section className="space-y-4">
    <CompletedRoster daily={daily} state={state} />
    <div className="flex flex-wrap justify-center gap-3">
      <button ref={resultButtonRef} className="btn" onClick={() => setOpen(true)}>{pl ? 'Twój wynik' : 'Your result'}</button>
      <Link href="/archiwum" className="btn">{pl ? 'Poprzednie plansze' : 'Previous boards'}</Link>
    </div>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <div className="picker-backdrop absolute inset-0" onClick={() => setOpen(false)} />
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className="panel relative max-h-[calc(100dvh-24px)] w-full max-w-lg overflow-y-auto p-5 sm:p-7 scroll-thin">
        <div className="mb-6 flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-xl font-semibold">{pl ? 'Gra zakończona' : 'Game finished'}</h2>
          <button onClick={() => setOpen(false)} aria-label={pl ? 'Zamknij' : 'Close'} className="h-8 w-8 shrink-0 text-2xl leading-none">×</button>
        </div>
        <ScoreDistribution dailyId={daily.id} userScore={state.total_points} compact />
        <FinalNicknamePrompt eligible={state.is_over && !state.is_practice} />
        <div className="mt-6 flex flex-wrap justify-center gap-3 border-t pt-5" style={{ borderColor: 'var(--line)' }}>
          <Link href="/archiwum" className="btn">{pl ? 'Poprzednie plansze' : 'Previous boards'}</Link>
          <Link href="/leaderboard" className="btn">{pl ? 'Ranking' : 'Leaderboard'}</Link>
        </div>
      </div>
    </div>}
  </section>
}
