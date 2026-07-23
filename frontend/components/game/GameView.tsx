'use client'
import { Daily, MAX_ERRORS } from '@/lib/api'
import RosterBoard from '@/components/roster/RosterBoard'
import GameLayout from '@/components/layout/GameLayout'
import AnswerStats from '@/components/results/AnswerStats'
import ArchiveList from '@/components/archive/ArchiveList'
import { useGame, useGameStore } from '@/lib/store'
import { useState, ReactNode } from 'react'

export default function GameView({
  daily,
  isLoading,
  error,
  showArchive = true,
  backLink,
}: {
  daily?: Daily,
  isLoading?: boolean,
  error?: unknown,
  showArchive?: boolean,
  backLink?: ReactNode,
}) {
  const [locale, setLocale] = useState<'pl' | 'en'>('pl')
  const game = useGame(daily?.id)
  const games = useGameStore(s => s.games)

  if (isLoading) return (
    <GameLayout locale={locale} onLocaleChange={(l) => setLocale(l as any)} errorsLeft={MAX_ERRORS}>
      <div className="text-center py-24 text-muted">Ładowanie Daily…</div>
    </GameLayout>
  )
  if (error || !daily) return (
    <GameLayout locale={locale} onLocaleChange={(l) => setLocale(l as any)} errorsLeft={MAX_ERRORS}>
      <div className="text-center py-20 text-red">
        Nie znaleziono tej zagadki.<br />
        <a href="/" className="mt-3 inline-block text-accent hover:underline text-sm">← Wróć do dzisiejszej</a>
      </div>
    </GameLayout>
  )

  const correct = daily.slots.filter(s => game.picks[s.id]?.is_correct).length
  const diamonds = daily.slots.filter(s => game.picks[s.id]?.is_diamond_pick).length
  const legendary = daily.slots.filter(s => game.picks[s.id]?.rarity_tier === 'legendary' && game.picks[s.id]?.is_correct).length

  const finishedGames = Object.values(games).filter(g => g.finished && g.score != null)
  const avg = finishedGames.length
    ? Math.round(finishedGames.reduce((s, g) => s + (g.score || 0), 0) / finishedGames.length * 10) / 10
    : null
  const best = finishedGames.length
    ? Math.min(...finishedGames.map(g => g.score || Infinity))
    : null
  const totalDiamonds = Object.values(games).reduce(
    (s, g) => s + Object.values(g.picks).filter(p => p.is_diamond_pick).length, 0
  )

  const leftTop = (
    <div className="flex items-baseline gap-3">
      {backLink}
      <div>
        <div className="text-[11px] text-muted uppercase tracking-wider">Daily #{daily.id}</div>
        <div className="text-[15px] font-bold text-ink">
          Wynik: <span className="text-accent mono">{game.finished && game.score != null ? `${game.score} pkt` : '—'}</span>
          <span className="text-muted font-normal text-[12px] ml-2">{daily.date}</span>
        </div>
      </div>
    </div>
  )

  const rightTop = (
    <div className="text-right flex items-center gap-4">
      {/* Compact stats */}
      {finishedGames.length > 0 && (
        <div className="hidden sm:flex items-center gap-3 text-[11px] text-muted">
          <span>Średni: <b className="text-ink">{avg}</b></span>
          <span>Best: <b className="text-accent">{best}</b></span>
          <span>◆ <b className="text-ink">{totalDiamonds}</b></span>
        </div>
      )}
      <div>
        <div className="text-[11px] text-muted">Trafione</div>
        <div className="text-[15px] font-bold text-ink">{correct}<span className="text-muted">/{daily.slots.length}</span></div>
      </div>
    </div>
  )

  return (
    <GameLayout
      locale={locale}
      onLocaleChange={(l) => setLocale(l as any)}
      leftTopSlot={leftTop}
      rightTopSlot={rightTop}
      errorsLeft={Math.max(0, MAX_ERRORS - game.errors)}
    >
      <div className="space-y-5">
        {/* Role cards + status bar */}
        <RosterBoard daily={daily} />

        {/* Game finished message */}
        {game.finished && (
          <div className="text-center text-[13px] text-warn font-medium">
            ✓ Gra zakończona – wynik <b className="mono">{game.score} pkt</b>
          </div>
        )}

        {/* Post-game results */}
        {game.finished && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2 text-[12px]">
              {[
                { k: 'Poprawne', v: `${correct}/${daily.slots.length}`, c: 'text-warn' },
                { k: 'Legendary', v: `${legendary}`, c: 'text-warn' },
                { k: 'Diamond', v: `${diamonds}`, c: 'text-ink' },
              ].map(x => (
                <div key={x.k} className="bg-panel border border-line rounded-console px-3 py-2 text-center">
                  <div className="text-muted text-[10px] uppercase">{x.k}</div>
                  <div className={`text-lg font-bold ${x.c}`}>{x.v}</div>
                </div>
              ))}
            </div>
            <AnswerStats daily={daily} />
          </div>
        )}

        {/* Archive */}
        {showArchive && <ArchiveList currentId={daily.id} />}
      </div>
    </GameLayout>
  )
}
