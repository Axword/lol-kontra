'use client'
import { useState } from 'react'
import { LeaderboardEntry, LeaderboardLimit, useLeaderboard } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { useGuestToken } from '@/lib/guest-profile'
import { formatPoints } from '@/lib/points'
import GameLayout from '@/components/layout/GameLayout'
import LoadError from '@/app/load-error'

export default function LeaderboardPage() {
  const locale = usePrefs((s) => s.locale)
  const token = useGuestToken()
  const [limit, setLimit] = useState<LeaderboardLimit>(50)
  const { data, isLoading, isError, refetch } = useLeaderboard(undefined, !!token, { limit, guestToken: token })
  const rows = (data?.results || []).slice(0, limit)
  const current = data?.current_player ?? null
  const row = (entry: LeaderboardEntry, key: string, own = false) => <tr key={key} data-current-player={own || undefined}
    className={`border-b last:border-b-0 ${own ? 'border-t-2' : ''}`}
    style={{ borderColor: own ? 'var(--gold)' : 'var(--line-soft)', background: own ? '#eef5ef' : undefined }}>
    <td className="px-4 py-5 tabular" style={{ color: entry.rank != null && entry.rank <= 3 ? 'var(--gold)' : 'var(--text-dim)' }}>{entry.rank ?? '—'}</td>
    <td className="break-words px-2 py-5 font-medium"><span className={own ? 'underline underline-offset-4' : undefined}>{entry.username}</span>
      {own && <span className="ml-2 text-xs" style={{ color: 'var(--gold)' }}>{locale === 'pl' ? 'Ty' : 'You'}</span>}</td>
    <td className="px-4 py-5 text-right font-semibold tabular" style={{ color: 'var(--gold)' }}>{entry.avg_points == null ? '—' : formatPoints(entry.avg_points, locale)}</td>
    <td className="hidden px-5 py-5 text-right tabular sm:table-cell" style={{ color: 'var(--text-dim)' }}>{entry.games_played}</td>
  </tr>

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header className="space-y-2">
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{locale === 'pl' ? 'Ranking' : 'Leaderboard'}</h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Średni wynik z oficjalnych plansz. Im mniej, tym lepiej.'
              : 'Average score across official boards. Lower is better.'}
          </p>
          <label className="flex items-center gap-3 pt-2 text-xs" style={{ color: 'var(--text-dim)' }}>
            <span>{locale === 'pl' ? 'Liczba graczy' : 'Number of players'}</span>
            <select value={limit} onChange={(event) => setLimit(Number(event.target.value) as LeaderboardLimit)} className="min-h-10 border bg-white px-3 text-sm tabular" style={{ borderColor: 'var(--line)' }}>
              {([10, 25, 50, 100] as const).map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </header>

        <div className="border bg-white" style={{ borderColor: 'var(--line)' }}>
          {!token || isLoading ? (
            <p role="status" className="px-6 py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              {locale === 'pl' ? 'Wczytywanie…' : 'Loading…'}
            </p>
          ) : isError ? (
            <LoadError onRetry={() => { void refetch() }} />
          ) : rows.length === 0 && !current ? (
            <p className="px-6 py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              {locale === 'pl'
                ? 'Ranking jest jeszcze pusty.'
                : 'The ranking is still empty.'}
            </p>
          ) : (
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr className="border-b text-xs" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)', background: 'var(--bg)' }}>
                  <th className="w-12 px-4 py-4 text-left font-medium sm:w-16">#</th>
                  <th className="px-2 py-4 text-left font-medium">{locale === 'pl' ? 'Gracz' : 'Player'}</th>
                  <th className="w-24 px-4 py-4 text-right font-medium">{locale === 'pl' ? 'Średnia' : 'Average'}</th>
                  <th className="hidden w-24 px-5 py-4 text-right font-medium sm:table-cell">
                    {locale === 'pl' ? 'Gry' : 'Games'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((entry, index) => row(entry, `top-${index}`))}
                {current && row(current, 'current-player', true)}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </GameLayout>
  )
}
