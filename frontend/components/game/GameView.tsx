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
    <div className="text-right">
      <div className="text-[11px] text-muted">Trafione</div>
      <div className="text-[15px] font-bold text-ink">{correct}<span className="text-muted">/{daily.slots.length}</span></div>
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
      <div className="space-y-6">
        {/* Match console – map | roster in one instrument */}
        <RosterBoard daily={daily} />

        {/* info under map */}
        <div className="text-center text-[13px] text-muted -mt-2">
          {game.finished
            ? `✓ Gra zakończona – wynik ${game.score} pkt`
            : 'Wybierz pozycje na mapie by zgadywać'}
        </div>

        {/* Results – show after finish */}
        {game.finished && (
          <div className="space-y-4">
            <div className="grid md:grid-cols-3 gap-3 text-[12px]">
              {[
                { k: 'Poprawne', v: `${correct}/${daily.slots.length}`, c: 'text-warn' },
                { k: 'Legendary', v: `${legendary}`, c: 'text-warn' },
                { k: 'Diamond', v: `${diamonds}`, c: 'text-ink' },
              ].map(x => (
                <div key={x.k} className="bg-panel border border-line rounded-console px-3 py-2 text-center">
                  <div className="text-muted text-[11px]">{x.k}</div>
                  <div className={`text-lg font-bold ${x.c}`}>{x.v}</div>
                </div>
              ))}
            </div>
            <AnswerStats daily={daily} />
          </div>
        )}

        {/* Stats + tips */}
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 panel">
            <div className="text-[11px] text-muted uppercase mb-2">Jak liczony jest wynik?</div>
            <div className="text-sm text-ink/90 leading-relaxed">
              Startujesz z <b className="text-ink">500 pkt</b>. Każde trafienie <b>odejmuje</b> punkty –
              im rzadszy pick, tym więcej odejmiesz (<b className="text-accent">niższy wynik = lepszy</b>).<br />
              <span className="text-muted text-[13px]">
                Przykład: pick wybierany przez 20% graczy → -80 pkt. Pick wybierany przez 0.5% → -99.5 pkt.
                Najrzadszy poprawny pick w slocie to <span className="text-ink font-semibold">◆ Diamond</span> – pełne -100.
              </span>
            </div>
          </div>
          <div className="space-y-3">
            <div className="panel">
              <div className="text-[11px] text-muted uppercase mb-1">Twoje staty</div>
              <div className="text-sm space-y-1 text-ink/90">
                <div>Rozegrane: <b>{finishedGames.length}</b></div>
                <div>Średni wynik: <b>{avg ?? '—'}</b></div>
                <div>Najlepszy: <b className="text-accent">{best ?? '—'}</b></div>
                <div>Diamond Picks: <b className="text-ink">{totalDiamonds} ◆</b></div>
              </div>
              <div className="text-[10px] text-muted mt-2">zapisywane lokalnie w przeglądarce</div>
            </div>
            <div className="panel text-[11px] text-muted leading-relaxed">
              <b className="text-ink">Tip:</b> Rzadkie picki = lepszy wynik.<br />
              Sprawdź historię drużyn, lata Worlds – tam są ukryte perełki.
            </div>
          </div>
        </div>

        {/* Archive */}
        {showArchive && <ArchiveList currentId={daily.id} />}
      </div>
    </GameLayout>
  )
}
