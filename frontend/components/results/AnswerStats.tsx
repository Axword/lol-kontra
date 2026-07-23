'use client'
import { Daily, rarityForPercent } from '@/lib/api'
import { useGame } from '@/lib/store'
import { useState } from 'react'

const tierColor: Record<string, string> = {
  common: 'text-zinc-300',
  rare: 'text-[#60a5fa]',
  epic: 'text-[#c084fc]',
  legendary: 'text-[#fbbf24]',
}

/**
 * Po zakończeniu gry – pokazuje wszystkie poprawne odpowiedzi
 * dla każdego slotu wraz z pick % (dane z pliku daily JSON).
 */
export default function AnswerStats({ daily }: { daily: Daily }) {
  const game = useGame(daily.id)
  const [selectedRole, setSelectedRole] = useState(daily.slots[0]?.role || 'top')

  if (!game.finished) return null

  const slot = daily.slots.find(s => s.role === selectedRole) || daily.slots[0]
  if (!slot) return null

  const myPick = game.picks[slot.id]

  return (
    <div className="card-lol">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 className="font-bold">Wszystkie poprawne odpowiedzi</h3>
        <div className="flex gap-1.5">
          {daily.slots.map(s => (
            <button
              key={s.id}
              onClick={() => setSelectedRole(s.role)}
              className={`px-2.5 py-1 rounded-lg border text-[11px] uppercase transition ${selectedRole === s.role
                ? 'border-[#C89B3C] text-[#C89B3C] bg-[#C89B3C]/10'
                : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
            >{s.role}</button>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-zinc-500 mb-2">
        {slot.conditions.map(c => c.label_pl).join(' • ')} — {slot.answers.length} poprawnych odpowiedzi
      </div>

      <div className="max-h-[340px] overflow-y-auto pr-1">
        <table className="w-full text-[13px]">
          <thead className="text-[11px] text-zinc-400 border-b border-zinc-800 sticky top-0 bg-[#0f141b]">
            <tr className="[&>th]:py-2 [&>th]:font-medium [&>th]:text-left">
              <th className="w-8">#</th>
              <th>Zawodnik</th>
              <th className="text-right">pick %</th>
              <th className="text-right">strata</th>
              <th className="text-center w-10">💎</th>
            </tr>
          </thead>
          <tbody>
            {slot.answers.map(([slug, pct], i) => {
              const isMine = myPick?.playerSlug === slug && myPick.is_correct
              const isDiamond = slot.diamond === slug
              const tier = rarityForPercent(pct)
              return (
                <tr key={slug} className={`border-b border-zinc-900 last:border-0 ${isMine ? 'bg-[#C89B3C]/10' : 'hover:bg-zinc-900/40'}`}>
                  <td className="py-[8px] text-zinc-500">{i + 1}</td>
                  <td className={`py-[8px] font-medium ${tierColor[tier]}`}>
                    {slug}
                    {isMine && <span className="ml-2 text-[10px] text-[#C89B3C] font-bold">← TY</span>}
                  </td>
                  <td className="py-[8px] text-right text-zinc-300">{pct.toFixed(1)}%</td>
                  <td className="py-[8px] text-right text-zinc-400">-{isDiamond ? '100.0' : (100 - pct).toFixed(1)}</td>
                  <td className="py-[8px] text-center">{isDiamond ? '💎' : ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="text-[10px] text-zinc-500 mt-2">
        pick % = szacowana popularność wyboru • 💎 = diamond pick (najrzadszy, -100) •
        <span className="text-[#60a5fa]"> rare</span> •
        <span className="text-[#c084fc]"> epic</span> •
        <span className="text-[#fbbf24]"> legendary</span>
      </div>
    </div>
  )
}
