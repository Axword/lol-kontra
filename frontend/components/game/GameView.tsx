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
      <div className="text-center py-24 text-zinc-400">Ładowanie Daily…</div>
    </GameLayout>
  )
  if (error || !daily) return (
    <GameLayout locale={locale} onLocaleChange={(l) => setLocale(l as any)} errorsLeft={MAX_ERRORS}>
      <div className="text-center py-20 text-red-400">
        Nie znaleziono tej zagadki.<br />
        <a href="/" className="mt-3 inline-block text-[#C89B3C] hover:underline text-sm">← Wróć do dzisiejszej</a>
      </div>
    </GameLayout>
  )

  const correct = daily.slots.filter(s => game.picks[s.id]?.is_correct).length
  const diamonds = daily.slots.filter(s => game.picks[s.id]?.is_diamond_pick).length
  const legendary = daily.slots.filter(s => game.picks[s.id]?.rarity_tier === 'legendary' && game.picks[s.id]?.is_correct).length

  // proste lokalne staty gracza (z localStorage)
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
        <div className="text-[11px] text-zinc-400 uppercase tracking-wider">Daily #{daily.id}</div>
        <div className="text-[15px] font-bold text-white">
          Wynik: <span className="text-[#C89B3C]">{game.finished && game.score != null ? `${game.score} pkt` : '—'}</span>
          <span className="text-zinc-500 font-normal text-[12px] ml-2">{daily.date}</span>
        </div>
      </div>
    </div>
  )

  const rightTop = (
    <div className="text-right">
      <div className="text-[11px] text-zinc-400">Trafione</div>
      <div className="text-[15px] font-bold">{correct}<span className="text-zinc-500">/{daily.slots.length}</span></div>
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
        {/* Game board */}
        <RosterBoard daily={daily} />

        {/* info under map */}
        <div className="text-center text-[13px] text-zinc-400 -mt-2">
          {game.finished
            ? `✅ Gra zakończona – wynik ${game.score} pkt`
            : '👆 Wybierz pozycje na mapie by zgadywać'}
        </div>

        {/* Results – show after finish */}
        {game.finished && (
          <div className="space-y-4">
            <div className="grid md:grid-cols-3 gap-3 text-[12px]">
              {[
                { k: 'Poprawne', v: `${correct}/${daily.slots.length}`, c: 'text-emerald-400' },
                { k: 'Legendary', v: `${legendary}`, c: 'text-[#F59E0B]' },
                { k: 'Diamond', v: `${diamonds}`, c: 'text-[#22D3EE]' },
              ].map(x => (
                <div key={x.k} className="bg-[#0f141b] border border-zinc-800 rounded-xl px-3 py-2 text-center">
                  <div className="text-zinc-400 text-[11px]">{x.k}</div>
                  <div className={`text-lg font-bold ${x.c}`}>{x.v}</div>
                </div>
              ))}
            </div>
            <AnswerStats daily={daily} />
          </div>
        )}

        {/* Stats + tips */}
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 card-lol">
            <div className="text-[11px] text-zinc-400 uppercase mb-2">Jak liczony jest wynik?</div>
            <div className="text-sm text-zinc-300 leading-relaxed">
              Startujesz z <b className="text-white">500 pkt</b>. Każde trafienie <b>odejmuje</b> punkty –
              im rzadszy pick, tym więcej odejmiesz (<b className="text-[#C89B3C]">niższy wynik = lepszy</b>).<br />
              <span className="text-zinc-400 text-[13px]">
                Przykład: pick wybierany przez 20% graczy → -80 pkt. Pick wybierany przez 0.5% → -99.5 pkt.
                Najrzadszy poprawny pick w slocie to <span className="text-[#22D3EE]">💎 Diamond</span> – pełne -100.
              </span>
            </div>
          </div>
          <div className="space-y-3">
            <div className="card-lol">
              <div className="text-[11px] text-zinc-400 uppercase mb-1">Twoje staty</div>
              <div className="text-sm space-y-1 text-zinc-300">
                <div>Rozegrane: <b>{finishedGames.length}</b></div>
                <div>Średni wynik: <b>{avg ?? '—'}</b></div>
                <div>Najlepszy: <b className="text-[#C89B3C]">{best ?? '—'}</b></div>
                <div>Diamond Picks: <b className="text-[#22D3EE]">{totalDiamonds} 💎</b></div>
              </div>
              <div className="text-[10px] text-zinc-500 mt-2">zapisywane lokalnie w przeglądarce</div>
            </div>
            <div className="card-lol text-[11px] text-zinc-400 leading-relaxed">
              <b className="text-zinc-200">Tip:</b> Rzadkie picki = lepszy wynik.<br />
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
