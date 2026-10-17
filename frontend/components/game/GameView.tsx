'use client'
import { ReactNode } from 'react'
import { Daily, MAX_ERRORS } from '@/lib/api'
import { useGame, usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'
import RosterBoard from '@/components/roster/RosterBoard'
import AnswerStats from '@/components/results/AnswerStats'
import ArchiveList from '@/components/archive/ArchiveList'

export default function GameView({
  daily, isLoading, error, showArchive = true, backLink,
}: {
  daily?: Daily
  isLoading?: boolean
  error?: unknown
  showArchive?: boolean
  backLink?: ReactNode
}) {
  const locale = usePrefs(s => s.locale)
  const game = useGame(daily?.id)

  if (isLoading) {
    return (
      <GameLayout>
        <p className="text-center py-24 text-muted text-[13px]">
          {locale === 'pl' ? 'Wczytywanie planszy…' : 'Loading the board…'}
        </p>
      </GameLayout>
    )
  }

  if (error || !daily) {
    return (
      <GameLayout>
        <div className="panel max-w-md mx-auto mt-12 p-6 text-center">
          <p className="text-ink mb-2">
            {locale === 'pl' ? 'Nie znaleziono tej zagadki.' : 'Puzzle not found.'}
          </p>
          <a href="/" className="btn btn-ghost text-[12px]">
            {locale === 'pl' ? 'Wróć do dzisiejszej' : 'Back to today'}
          </a>
        </div>
      </GameLayout>
    )
  }

  const correct = daily.slots.filter(s => game.picks[s.id]?.is_correct).length
  const diamonds = daily.slots.filter(s => game.picks[s.id]?.is_diamond_pick).length
  const legendary = daily.slots.filter(
    s => game.picks[s.id]?.is_correct && game.picks[s.id]?.rarity_tier === 'legendary'
  ).length

  return (
    <GameLayout
      dailyId={daily.id}
      dailyDate={daily.date}
      score={game.finished ? game.score : null}
      correct={correct}
      slotsTotal={daily.slots.length}
      errorsLeft={Math.max(0, MAX_ERRORS - game.errors)}
      errorsTotal={MAX_ERRORS}
    >
      <div className="space-y-4">
        {backLink && <div className="text-[12px]">{backLink}</div>}

        <RosterBoard daily={daily} />

        {/*
          Podsumowanie pojawia się dopiero po zakończeniu gry. Wcześniej ekran
          gry zawierał na stałe kartę "Jak liczony jest wynik", kartę "Twoje
          staty" z zerami i kartę z poradą – łącznie trzy panele tekstu nad
          archiwum, które nie zmieniały się nigdy. Zasady są w oknie pomocy,
          statystyki na stronie /profile.
        */}
        {game.finished && (
          <section className="space-y-3">
            <div className="console p-5">
              <div className="eyebrow mb-2">
                {correct === daily.slots.length
                  ? (locale === 'pl' ? 'Komplet' : 'Full board')
                  : (locale === 'pl' ? 'Koniec gry' : 'Game over')}
              </div>
              <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
                <div>
                  <div className="mono text-[38px] leading-none text-ink">{game.score ?? '—'}</div>
                  <div className="eyebrow mt-1">
                    {locale === 'pl' ? 'punktów – im mniej, tym lepiej' : 'points – lower is better'}
                  </div>
                </div>
                <div>
                  <div className="mono text-[22px] leading-none text-ink">
                    {correct}<span className="text-muted">/{daily.slots.length}</span>
                  </div>
                  <div className="eyebrow mt-1">{locale === 'pl' ? 'trafionych' : 'correct'}</div>
                </div>
                <div>
                  <div className="mono text-[22px] leading-none text-ink">
                    {game.errors}<span className="text-muted">/{MAX_ERRORS}</span>
                  </div>
                  <div className="eyebrow mt-1">{locale === 'pl' ? 'pomyłek' : 'misses'}</div>
                </div>
                {legendary > 0 && (
                  <div>
                    <div className="mono text-[22px] leading-none r-legendary">{legendary}</div>
                    <div className="eyebrow mt-1">{locale === 'pl' ? 'legendarnych' : 'legendary'}</div>
                  </div>
                )}
                {diamonds > 0 && (
                  <div>
                    <div className="mono text-[22px] leading-none r-diamond">{diamonds}</div>
                    <div className="eyebrow mt-1">
                      {locale === 'pl' ? 'najrzadszych picków' : 'rarest picks'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <AnswerStats daily={daily} />
          </section>
        )}

        {showArchive && <ArchiveList currentId={daily.id} />}
      </div>
    </GameLayout>
  )
}
