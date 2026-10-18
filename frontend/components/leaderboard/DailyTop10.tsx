'use client'
import Link from 'next/link'
import { useLeaderboard } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import LoadError from '@/app/load-error'

type Entry = {
  username: string
  total_points: number
  diamond_picks?: number
  legendary_answers?: number
}

export default function DailyTop10({ dailyId, limit = 10 }: { dailyId?: number; limit?: number }) {
  const locale = usePrefs((s) => s.locale)
  const { data, isLoading, isError, refetch } = useLeaderboard(dailyId)
  const rows: Entry[] = (data?.results || []).slice(0, limit)

  return (
    <div className="min-w-0 border bg-white" style={{ borderColor: 'var(--line)' }}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 border-b px-5 py-5" style={{ borderColor: 'var(--line)' }}>
        <h2 className="text-base font-semibold">
          {dailyId
            ? (locale === 'pl' ? 'Ranking planszy' : 'Board ranking')
            : (locale === 'pl' ? 'Najlepsi ogółem' : 'All-time top')}
        </h2>
        <Link href="/leaderboard" className="text-xs underline-offset-4 hover:underline" style={{ color: 'var(--gold)' }}>
          {locale === 'pl' ? 'pełny ranking' : 'full ranking'}
        </Link>
      </div>

      {isLoading ? (
        <p className="px-5 py-8 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
          {locale === 'pl' ? 'Wczytywanie…' : 'Loading…'}
        </p>
      ) : isError ? (
        <LoadError onRetry={() => { void refetch() }} />
      ) : rows.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
          {locale === 'pl' ? 'Brak wyników do pokazania.' : 'No results yet.'}
        </p>
      ) : (
        <ol>
          {rows.map((r, i) => (
            <li
              key={`${r.username}-${i}`}
              className="flex items-center gap-3 border-b px-5 py-4 text-sm last:border-b-0"
              style={{ borderColor: 'var(--line-soft)' }}
            >
              <span className="w-5 shrink-0 tabular" style={{ color: i < 3 ? 'var(--gold)' : 'var(--text-dim)' }}>
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 break-words">{r.username}</span>
              <span className="font-semibold tabular" style={{ color: 'var(--gold)' }}>{Math.round(r.total_points)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
