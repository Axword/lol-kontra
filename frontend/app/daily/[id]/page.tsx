'use client'
import { useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useDaily, useGameState } from '@/lib/api'
import { isAvailableDaily, isValidDailyId, useGameDate } from '@/lib/daily'
import axios from 'axios'
import { usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'
import RosterBoard from '@/components/roster/RosterBoard'
import GameSummary from '@/components/results/GameSummary'
import LoadError from '@/app/load-error'
import DailyCommunity from '@/components/community/DailyCommunity'
import PreviousChallenges from '@/components/archive/PreviousChallenges'

export default function ArchivedDailyPage() {
  const params = useParams()
  const id = Number(params?.id)
  const today = useGameDate()
  const locale = usePrefs((s) => s.locale)
  const guestToken = usePrefs((s) => s.guestToken)
  const ensureGuestToken = usePrefs((s) => s.ensureGuestToken)

  useEffect(() => { ensureGuestToken() }, [ensureGuestToken])

  const daily = useDaily(id)
  const available = !!daily.data && isAvailableDaily(daily.data, today)
  const game = useGameState(available ? daily.data?.id : undefined, guestToken)
  const state = game.data

  if (daily.isLoading) {
    return (
      <GameLayout>
        <p className="py-20 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
          {locale === 'pl' ? 'Wczytywanie planszy…' : 'Loading the board…'}
        </p>
      </GameLayout>
    )
  }

  if (!isValidDailyId(id) || (daily.data && !available) || (axios.isAxiosError(daily.error) && daily.error.response?.status === 404)) {
    return (
      <GameLayout>
        <div className="panel p-6 max-w-md mx-auto mt-12 text-center">
          <p className="display text-[17px] mb-2">
            {locale === 'pl' ? 'Nie znaleziono planszy' : 'Board not found'}
          </p>
          <Link href="/archiwum" className="btn cut-sm mt-2">
            {locale === 'pl' ? 'Wróć do archiwum' : 'Back to archive'}
          </Link>
        </div>
      </GameLayout>
    )
  }

  if (daily.error || !daily.data) {
    return <GameLayout><LoadError onRetry={() => { void daily.refetch() }} archive /></GameLayout>
  }

  return (
    <GameLayout
      dailyId={daily.data.id}
      dailyDate={daily.data.date}
      score={state ? state.total_points : null}
      correctCount={state?.correct_count ?? 0}
      slotsTotal={state?.slots_total ?? daily.data.slots.length}
      errorsLeft={state?.errors_left ?? null}
      maxErrors={state?.max_errors ?? null}
    >
      <div className="space-y-4 max-w-[1000px] mx-auto">
        <div
          className="panel-flat px-3 py-2 text-[12px] flex flex-wrap items-center justify-between gap-2"
          style={{ color: 'var(--text-dim)' }}
        >
          <span>
            {daily.data.date === today
              ? (locale === 'pl' ? 'Dzisiejsza plansza' : 'Today’s board')
              : locale === 'pl'
              ? 'Plansza archiwalna'
              : 'Archived board'}
          </span>
          <Link href="/archiwum" style={{ color: 'var(--gold-dim)' }}>
            {locale === 'pl' ? 'archiwum' : 'archive'}
          </Link>
        </div>

        {game.isError ? (
          <LoadError title={locale === 'pl' ? 'Nie udało się wczytać stanu gry' : 'Could not load game state'} onRetry={() => { void game.refetch() }} />
        ) : state ? (
          <>{state.is_over ? <GameSummary daily={daily.data} state={state} /> : <RosterBoard key={daily.data.id} daily={daily.data} state={state} />}</>
        ) : (
          <p className="py-16 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
            {locale === 'pl' ? 'Wczytywanie stanu gry…' : 'Loading game state…'}
          </p>
        )}

        <DailyCommunity key={`community-${daily.data.id}`} dailyId={daily.data.id} state={state} />
        <PreviousChallenges currentId={daily.data.id} />
      </div>
    </GameLayout>
  )
}
