'use client'
import { Daily, rarityForPercent, USE_API, API_BASE } from '@/lib/api'
import { useGame } from '@/lib/store'
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

const tierColor: Record<string, string> = {
  common: 'r-common',
  rare: 'r-rare',
  epic: 'r-epic',
  legendary: 'r-legendary',
}

/**
 * Po zakończeniu gry – pokazuje wszystkie poprawne odpowiedzi
 * dla każdego slotu wraz z pick % (dane z pliku daily JSON lub z API).
 */
export default function AnswerStats({ daily }: { daily: Daily }) {
  const game = useGame(daily.id)
  const [selectedRole, setSelectedRole] = useState(daily.slots[0]?.role || 'top')

  // In API mode, fetch answer stats from backend
  const { data: apiStats } = useQuery({
    queryKey: ['answer-stats', daily.id],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/dailies/${daily.id}/answer-stats/`)
      if (!r.ok) throw new Error('Failed to fetch answer stats')
      return r.json()
    },
    enabled: USE_API && !!game.finished,
    staleTime: 60_000,
  })

  if (!game.finished) return null

  const slot = daily.slots.find(s => s.role === selectedRole) || daily.slots[0]
  if (!slot) return null

  const myPick = game.picks[slot.id]

  // Build answers list: static mode uses slot.answers, API mode uses apiStats
  let answers: [string, number][] = []
  let diamondSlug = slot.diamond || ''

  if (USE_API && apiStats?.results) {
    const slotStats = apiStats.results
      .filter((s: any) => s.slot_id === slot.id)
      .sort((a: any, b: any) => b.pick_percent - a.pick_percent)
    answers = slotStats.map((s: any) => [s.player_slug || s.player, s.pick_percent])
    // Diamond is the one with lowest pick_percent
    if (slotStats.length > 0) {
      const rarest = slotStats[slotStats.length - 1]
      diamondSlug = rarest.player_slug || rarest.player
    }
  } else {
    answers = slot.answers
    diamondSlug = slot.diamond
  }

  return (
    <div className="panel">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 className="font-bold text-ink">Wszystkie poprawne odpowiedzi</h3>
        <div className="flex gap-1.5">
          {daily.slots.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedRole(s.role)}
              className={`px-2.5 py-1 rounded-control border text-[11px] uppercase transition-colors ${selectedRole === s.role
                ? 'tonal'
                : 'border-line text-muted hover:border-muted hover:text-ink'}`}
            >{s.role}</button>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-muted mb-2">
        {slot.conditions.map(c => c.label_pl).join(' • ')} — {answers.length} poprawnych odpowiedzi
      </div>

      <div className="max-h-[340px] overflow-y-auto pr-1">
        <table className="w-full text-[13px]">
          <thead className="text-[11px] text-muted border-b border-line sticky top-0 bg-panel">
            <tr className="[&>th]:py-2 [&>th]:font-medium [&>th]:text-left">
              <th className="w-8">#</th>
              <th>Zawodnik</th>
              <th className="text-right">pick %</th>
              <th className="text-right">strata</th>
              <th className="text-center w-10">◆</th>
            </tr>
          </thead>
          <tbody>
            {answers.map(([slug, pct], i) => {
              const isMine = myPick?.playerSlug === slug && myPick.is_correct
              const isDiamond = diamondSlug === slug
              const tier = rarityForPercent(pct)
              return (
                <tr key={slug} className={`border-b border-line last:border-0 ${isMine ? 'bg-accent-soft' : 'hover:bg-surface/60'}`}>
                  <td className="py-[8px] text-muted">{i + 1}</td>
                  <td className={`py-[8px] font-medium ${tierColor[tier]}`}>
                    {slug}
                    {isMine && <span className="ml-2 text-[10px] text-accent font-bold">← TY</span>}
                  </td>
                  <td className="py-[8px] text-right text-ink/90">{pct.toFixed(1)}%</td>
                  <td className="py-[8px] text-right text-muted">-{isDiamond ? '100.0' : (100 - pct).toFixed(1)}</td>
                  <td className="py-[8px] text-center">{isDiamond ? '◆' : ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {answers.length === 0 && (
        <div className="text-center text-muted py-6 text-[12px]">
          {USE_API ? 'Statystyki odpowiedzi dostępne po zakończeniu dnia' : 'Brak danych'}
        </div>
      )}

      <div className="text-[10px] text-muted mt-2">
        pick % = szacowana popularność wyboru • ◆ = diamond pick (najrzadszy, -100) •
        <span className="r-rare"> rare</span> •
        <span className="r-epic"> epic</span> •
        <span className="r-legendary"> legendary</span>
      </div>
    </div>
  )
}
