'use client'
import { useState } from 'react'
import { LeaderboardEntry, LeaderboardLimit, LeaderboardMode, useLeaderboard } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import { useGuestToken } from '@/lib/guest-profile'
import { formatPoints } from '@/lib/points'
import GameLayout from '@/components/layout/GameLayout'
import LoadError from '@/app/load-error'

export default function LeaderboardPage() {
  const locale = usePrefs((s) => s.locale)
  const token = useGuestToken()
  const [limit, setLimit] = useState<LeaderboardLimit>(50)
  const [page, setPage] = useState(1)
  const [mode, setMode] = useState<LeaderboardMode>('weighted')
  const { data, isLoading, isError, refetch } = useLeaderboard(undefined, !!token, { limit, guestToken: token, page, mode })
  const rows = (data?.results || []).slice(0, limit)
  const currentPage = data?.page ?? page
  const totalPages = data?.total_pages ?? Math.max(1, Math.ceil((data?.total_players ?? 0) / limit))
  const current = data?.current_player ?? null
  const row = (entry: LeaderboardEntry, key: string, own = false) => <tr key={key} data-current-player={own || undefined}
    className={`border-b last:border-b-0 ${own ? 'border-t-2' : ''}`}
    style={{ borderColor: own ? 'var(--gold)' : 'var(--line-soft)', background: own ? '#eef5ef' : undefined }}>
    <td className="px-4 py-5 tabular" style={{ color: entry.rank != null && entry.rank <= 3 ? 'var(--gold)' : 'var(--text-dim)' }}>{entry.rank ?? '—'}</td>
    <td className="break-words px-2 py-5 font-medium"><span className={own ? 'underline underline-offset-4' : undefined}>{entry.username}</span>
      {own && <span className="ml-2 text-xs" style={{ color: 'var(--gold)' }}>{locale === 'pl' ? 'Ty' : 'You'}</span>}</td>
    <td className="px-3 py-5 text-right font-semibold tabular" style={{ color: 'var(--gold)' }}>{entry.weighted_points == null ? '—' : formatPoints(entry.weighted_points, locale)}</td>
    <td className="px-3 py-5 text-right tabular">{entry.avg_points == null ? '—' : formatPoints(entry.avg_points, locale)}</td>
    <td className="px-3 py-5 text-right tabular" style={{ color: 'var(--text-dim)' }}>{entry.games_played}</td>
    <td className="px-3 py-5 text-right tabular" style={{ color: 'var(--text-dim)' }}>{entry.games_played ? formatPoints(entry.total_points, locale) : '—'}</td>
  </tr>

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header className="space-y-2">
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{locale === 'pl' ? 'Ranking' : 'Leaderboard'}</h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Wyniki z oficjalnych plansz. Im mniej, tym lepiej. Wynik ważony uwzględnia średnią i liczbę gier (waga 5 gier).'
              : 'Official board scores. Lower is better. The weighted score combines your average and games played (5-game weight).'}
          </p>
          <label className="flex items-center gap-3 pt-2 text-xs" style={{ color: 'var(--text-dim)' }}>
            <span>{locale === 'pl' ? 'Graczy na stronie' : 'Players per page'}</span>
            <select value={limit} onChange={(event) => {setLimit(Number(event.target.value) as LeaderboardLimit);setPage(1)}} className="min-h-10 border bg-white px-3 text-sm tabular" style={{ borderColor: 'var(--line)' }}>
              {([10, 25, 50, 100] as const).map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <div className="flex flex-wrap gap-2 pt-2" role="group" aria-label={locale === 'pl' ? 'Sortowanie rankingu' : 'Leaderboard sorting'}>
            {(['weighted', 'average'] as const).map(value => <button key={value} aria-pressed={mode === value} className="min-h-10 border px-4 text-sm"
              style={{ borderColor: mode === value ? 'var(--gold)' : 'var(--line)', background: mode === value ? '#eef5ef' : '#fff' }}
              onClick={() => {setMode(value);setPage(1)}}>{value === 'weighted' ? (locale === 'pl' ? 'Ranking ważony' : 'Weighted ranking') : (locale === 'pl' ? 'Według średniej' : 'By average')}</button>)}
          </div>
          <details className="text-xs" style={{ color: 'var(--text-dim)' }}><summary className="cursor-pointer">{locale === 'pl' ? 'Jak liczymy wynik ważony?' : 'How is the weighted score calculated?'}</summary>
            <p className="mt-2">{locale === 'pl' ? '(Suma punktów gracza + 5 × średnia wszystkich ukończonych gier) / (liczba gier gracza + 5).' : '(Your total points + 5 × the average of all completed games) / (your games played + 5).'}</p>
          </details>
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
            <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b text-xs" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)', background: 'var(--bg)' }}>
                  <th className="w-12 px-4 py-4 text-left font-medium sm:w-16">#</th>
                  <th className="px-2 py-4 text-left font-medium">{locale === 'pl' ? 'Gracz' : 'Player'}</th>
                  <th className="w-24 px-3 py-4 text-right font-medium">{locale === 'pl' ? 'Ważony' : 'Weighted'}</th>
                  <th className="w-24 px-3 py-4 text-right font-medium">{locale === 'pl' ? 'Średnia' : 'Average'}</th>
                  <th className="w-20 px-3 py-4 text-right font-medium">
                    {locale === 'pl' ? 'Gry' : 'Games'}
                  </th>
                  <th className="w-24 px-3 py-4 text-right font-medium">{locale === 'pl' ? 'Suma' : 'Total'}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((entry, index) => row(entry, `top-${index}`))}
                {current && row(current, 'current-player', true)}
              </tbody>
            </table></div>
          )}
        </div>
        {data && !isLoading && !isError && totalPages > 1 && <nav className="flex flex-wrap items-center justify-between gap-3 text-sm" aria-label={locale === 'pl' ? 'Strony rankingu' : 'Leaderboard pages'}>
          <div className="flex gap-2"><button className="min-h-10 border px-3 disabled:opacity-40" disabled={currentPage <= 1} onClick={() => setPage(1)}>{locale === 'pl' ? 'Pierwsza' : 'First'}</button>
            <button className="min-h-10 border px-3 disabled:opacity-40" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>{locale === 'pl' ? 'Poprzednia' : 'Previous'}</button></div>
          <label className="flex items-center gap-2">{locale === 'pl' ? 'Strona' : 'Page'}<input aria-label={locale === 'pl' ? 'Numer strony' : 'Page number'} type="number" min={1} max={totalPages} value={currentPage}
            className="w-16 border bg-white px-2 py-2" onChange={event => {const value = Number(event.target.value);if(Number.isInteger(value) && value >= 1 && value <= totalPages) setPage(value)}} /> / {totalPages}</label>
          <div className="flex gap-2"><button className="min-h-10 border px-3 disabled:opacity-40" disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)}>{locale === 'pl' ? 'Następna' : 'Next'}</button>
            <button className="min-h-10 border px-3 disabled:opacity-40" disabled={currentPage >= totalPages} onClick={() => setPage(totalPages)}>{locale === 'pl' ? 'Ostatnia' : 'Last'}</button></div>
        </nav>}
      </div>
    </GameLayout>
  )
}
