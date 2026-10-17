'use client'
import { useMemo, useState } from 'react'
import { Daily, rarityForPercent, usePlayers } from '@/lib/api'
import { rarityClass, roleLabel } from '@/lib/flags'
import { useGame, usePrefs } from '@/lib/store'

/**
 * Po zakończeniu gry – pokazuje wszystkie poprawne odpowiedzi
 * dla każdego slotu wraz z pick % (dane z pliku daily JSON).
 */
export default function AnswerStats({ daily }: { daily: Daily }) {
  const locale = usePrefs(s => s.locale)
  const game = useGame(daily.id)
  const { data: players } = usePlayers()
  const [selectedRole, setSelectedRole] = useState(daily.slots[0]?.role || 'top')

  // Tabela pokazywała surowe slugi ("ning", "jackeylove") zamiast nicków.
  const nameOf = useMemo(() => {
    const map = new Map((players || []).map(p => [p.slug, p.nickname]))
    return (slug: string) => map.get(slug) || slug
  }, [players])

  if (!game.finished) return null

  const slot = daily.slots.find(s => s.role === selectedRole) || daily.slots[0]
  if (!slot) return null

  const myPick = game.picks[slot.id]

  return (
    <div className="panel">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 className="text-[15px] font-semibold text-ink">
          {locale === 'pl' ? 'Wszystkie poprawne odpowiedzi' : 'All correct answers'}
        </h3>
        <div className="flex gap-1.5">
          {daily.slots.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedRole(s.role)}
              className={`px-2.5 py-1 rounded-control border text-[11px] uppercase transition-colors ${selectedRole === s.role
                ? 'tonal'
                : 'border-line text-muted hover:border-muted hover:text-ink'}`}
            >{roleLabel(s.role, locale)}</button>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-muted mb-2">
        {slot.conditions.map(c => (locale === 'pl' ? c.label_pl : c.label_en)).join(' · ')} — {slot.answers.length}{' '}
        {locale === 'pl' ? 'poprawnych odpowiedzi' : 'correct answers'}
      </div>

      <div className="max-h-[340px] overflow-y-auto pr-1">
        <table className="w-full text-[13px]">
          <thead className="text-[11px] text-muted border-b border-line sticky top-0 bg-panel">
            <tr className="[&>th]:py-2 [&>th]:font-medium [&>th]:text-left">
              <th className="w-8">#</th>
              <th>{locale === 'pl' ? 'Zawodnik' : 'Player'}</th>
              <th className="text-right">pick %</th>
              <th className="text-right">{locale === 'pl' ? 'strata' : 'deduction'}</th>
            </tr>
          </thead>
          <tbody>
            {slot.answers.map(([slug, pct], i) => {
              const isMine = myPick?.playerSlug === slug && myPick.is_correct
              const isDiamond = slot.diamond === slug
              const tier = rarityForPercent(pct)
              return (
                <tr key={slug} className={`border-b border-line last:border-0 ${isMine ? 'bg-accent-soft' : 'hover:bg-surface/60'}`}>
                  <td className="py-[8px] text-muted">{i + 1}</td>
                  <td className={`py-[8px] font-medium ${rarityClass[tier]}`}>
                    {nameOf(slug)}
                    {isDiamond && (
                      <span className="ml-2 text-[10px] r-diamond uppercase tracking-[0.1em]">
                        {locale === 'pl' ? 'najrzadszy' : 'rarest'}
                      </span>
                    )}
                    {isMine && (
                      <span className="ml-2 text-[10px] text-accent uppercase tracking-[0.1em]">
                        {locale === 'pl' ? 'twój wybór' : 'your pick'}
                      </span>
                    )}
                  </td>
                  <td className="py-[8px] text-right text-ink/90">{pct.toFixed(1)}%</td>
                  <td className="py-[8px] text-right text-muted">-{isDiamond ? '100.0' : (100 - pct).toFixed(1)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-muted mt-2">
        {locale === 'pl'
          ? 'pick % = szacowana popularność wyboru; najrzadsza poprawna odpowiedź daje pełne −100'
          : 'pick % = estimated popularity; the rarest correct answer gives the full −100'}
      </div>
    </div>
  )
}
