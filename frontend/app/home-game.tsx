'use client'
import { useEffect } from 'react'
import { useDailyToday, useGameState } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'
import RosterBoard from '@/components/roster/RosterBoard'
import GameSummary from '@/components/results/GameSummary'
import LoadError from './load-error'
import DailyCommunity from '@/components/community/DailyCommunity'
import PreviousChallenges from '@/components/archive/PreviousChallenges'

export default function HomePage() {
  const locale = usePrefs((s) => s.locale)
  const guestToken = usePrefs((s) => s.guestToken)
  const ensureGuestToken = usePrefs((s) => s.ensureGuestToken)

  useEffect(() => { ensureGuestToken() }, [ensureGuestToken])

  const daily = useDailyToday()
  const game = useGameState(daily.data?.id, guestToken)

  const state = game.data

  if (daily.isLoading) {
    return (
      <GameLayout>
        <div className="py-20 text-center">
          <h1 className="text-[28px] font-semibold">WORLDS KONTRA</h1>
          <p className="mt-3 text-[13px]" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Kontra Quiz League of Legends — dopasuj pięciu zawodników do wskazówek o Worlds i ich karierze.'
              : 'A daily League of Legends quiz — match five players to clues about Worlds and their careers.'}
          </p>
          <p className="mt-4 text-[13px]" style={{ color: 'var(--text-faint)' }}>
            {locale === 'pl' ? 'Wczytywanie planszy…' : 'Loading the board…'}
          </p>
        </div>
      </GameLayout>
    )
  }

  if (daily.error || !daily.data) {
    return (
      <GameLayout>
        <div className="panel p-6 max-w-md mx-auto mt-12 text-center">
          <p className="display text-[17px] mb-2">
            {locale === 'pl' ? 'Nie udało się wczytać planszy' : 'Could not load the board'}
          </p>
          <p className="text-[13px] mb-4" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Serwer gry nie odpowiada.'
              : 'The game server is not responding.'}
          </p>
          <button className="btn btn-gold cut-sm" onClick={() => daily.refetch()}>
            {locale === 'pl' ? 'Spróbuj ponownie' : 'Try again'}
          </button>
        </div>
      </GameLayout>
    )
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
      {daily.data.slots.length === 0 ? (
        <div className="panel p-6 text-center">
          <p className="display text-[16px] mb-1">
            {locale === 'pl' ? 'Plansza na dziś nie jest gotowa' : 'Today’s board is not ready'}
          </p>
          <p className="text-[13px]" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Zajrzyj za chwilę albo zagraj archiwalną planszę.'
              : 'Check back shortly or play an archived board.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4 max-w-[1000px] mx-auto">
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
      )}
    </GameLayout>
  )
}
