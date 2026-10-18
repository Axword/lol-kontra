'use client'
import { useLeaderboard } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'
import LoadError from '@/app/load-error'

export default function LeaderboardPage() {
  const locale = usePrefs((s) => s.locale)
  const { data, isLoading, isError, refetch } = useLeaderboard()
  const rows = data?.results || []

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header className="space-y-2">
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{locale === 'pl' ? 'Ranking' : 'Leaderboard'}</h1>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Suma punktów z oficjalnych plansz.'
              : 'Total points across official boards.'}
          </p>
        </header>

        <div className="border bg-white" style={{ borderColor: 'var(--line)' }}>
          {isLoading ? (
            <p className="px-6 py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              {locale === 'pl' ? 'Wczytywanie…' : 'Loading…'}
            </p>
          ) : isError ? (
            <LoadError onRetry={() => { void refetch() }} />
          ) : rows.length === 0 ? (
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
                  <th className="w-24 px-4 py-4 text-right font-medium">{locale === 'pl' ? 'Punkty' : 'Points'}</th>
                  <th className="hidden w-24 px-5 py-4 text-right font-medium sm:table-cell">
                    {locale === 'pl' ? 'Gry' : 'Games'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u: any, i: number) => (
                  <tr key={i} className="border-b last:border-b-0" style={{ borderColor: 'var(--line-soft)' }}>
                    <td className="px-4 py-5 tabular" style={{ color: i < 3 ? 'var(--gold)' : 'var(--text-dim)' }}>
                      {i + 1}
                    </td>
                    <td className="break-words px-2 py-5 font-medium">{u.username}</td>
                    <td className="px-4 py-5 text-right font-semibold tabular" style={{ color: 'var(--gold)' }}>
                      {Math.round(u.total_points)}
                    </td>
                    <td className="hidden px-5 py-5 text-right tabular sm:table-cell" style={{ color: 'var(--text-dim)' }}>
                      {u.games_played ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </GameLayout>
  )
}
