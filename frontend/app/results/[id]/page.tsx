'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api, useDaily } from '@/lib/api'
import { isAvailableDaily, isValidDailyId, useGameDate } from '@/lib/daily'
import axios from 'axios'
import { rarityColor, roleLabel, ROLE_ORDER } from '@/lib/flags'
import { rarityForPercent } from '@/lib/rarity'
import { usePrefs } from '@/lib/store'
import GameLayout from '@/components/layout/GameLayout'
import DailyTop10 from '@/components/leaderboard/DailyTop10'
import LoadError from '@/app/load-error'
import RarityIndicator from '@/components/roster/RarityIndicator'

type AnswerStat = {
  slot_id: number
  slot_role: string
  player: string
  player_slug: string
  pick_count: number
  pick_percent: number
  rarity_tier: string
}

export default function ResultsPage() {
  const params = useParams()
  const id = Number(params?.id)
  const today = useGameDate()
  const locale = usePrefs((s) => s.locale)
  const [role, setRole] = useState<string>('top')

  const daily = useDaily(id)
  const available = !!daily.data && isAvailableDaily(daily.data, today)

  const stats = useQuery({
    queryKey: ['answer-stats', id],
    queryFn: async ({ signal }) => (await api.get(`/dailies/${id}/answer-stats/`, { signal })).data,
    enabled: available,
    staleTime: 60_000,
  })

  const byRole = useMemo(() => {
    const rows: AnswerStat[] = stats.data?.results || []
    const map: Record<string, AnswerStat[]> = {}
    for (const r of rows) (map[r.slot_role] ||= []).push(r)
    for (const k of Object.keys(map)) map[k].sort((a, b) => b.pick_percent - a.pick_percent)
    return map
  }, [stats.data?.results])

  const current = byRole[role] || []
  const slot = daily.data?.slots.find((s) => s.role === role)

  if (!isValidDailyId(id) || (daily.data && !available) || (axios.isAxiosError(daily.error) && daily.error.response?.status === 404)) {
    return <GameLayout><LoadError title={locale === 'pl' ? 'Nie znaleziono planszy' : 'Board not found'} archive /></GameLayout>
  }
  if (daily.isLoading) {
    return <GameLayout><p className="p-6 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
      {locale === 'pl' ? 'Wczytywanie planszy…' : 'Loading the board…'}
    </p></GameLayout>
  }
  if (daily.isError || !daily.data) {
    return <GameLayout><LoadError onRetry={() => { void daily.refetch() }} archive /></GameLayout>
  }

  return (
    <GameLayout dailyId={daily.data?.id} dailyDate={daily.data?.date}>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header className="flex flex-wrap items-baseline justify-between gap-3">
          <div><h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">
            {locale === 'pl' ? 'Odpowiedzi graczy' : 'What players answered'}
          </h1>
          <p className="text-xs mt-2" style={{ color: 'var(--text-faint)' }}>
            {new Date(daily.data.date + 'T00:00:00').toLocaleDateString(locale === 'pl' ? 'pl-PL' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' })} · #{daily.data.id}
          </p></div>
          <Link href={`/daily/${id}`} className="text-sm font-medium underline-offset-4 hover:underline" style={{ color: 'var(--gold)' }}>
            {locale === 'pl' ? 'zagraj tę planszę' : 'play this board'}
          </Link>
        </header>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="min-w-0 border bg-[var(--panel)]" style={{ borderColor: 'var(--line)' }}>
        <div className="flex flex-wrap gap-1 border-b p-3" style={{ borderColor: 'var(--line)' }}>
          {ROLE_ORDER.map((r) => (
            <button
              key={r}
              aria-pressed={role === r}
              onClick={() => setRole(r)}
              className="min-h-10 flex-1 border px-2 py-2 text-[13px] transition-colors"
              style={
                role === r
                  ? { borderColor: 'var(--gold)', color: 'var(--gold)', background: 'var(--panel-2)', fontWeight: 600 }
                  : { borderColor: 'transparent', color: 'var(--text-dim)' }
              }
            >
              {roleLabel(r, locale)}
            </button>
          ))}
        </div>

        {slot && (
          <ul className="flex flex-wrap gap-x-6 gap-y-2 border-b px-5 py-5" style={{ borderColor: 'var(--line-soft)' }}>
            {slot.conditions.map((c) => (
              <li key={c.id} className="border-l-2 pl-3 text-sm" style={{ borderColor: 'var(--gold)', color: 'var(--text-dim)' }}>{locale === 'pl' ? c.label_pl : c.label_en}</li>
            ))}
          </ul>
        )}

        <div>
          {stats.isLoading ? (
            <p className="px-6 py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              {locale === 'pl' ? 'Wczytywanie…' : 'Loading…'}
            </p>
          ) : stats.isError ? (
            <LoadError title={locale === 'pl' ? 'Nie udało się wczytać odpowiedzi' : 'Could not load answers'} onRetry={() => { void stats.refetch() }} />
          ) : current.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
              {locale === 'pl'
                ? 'Brak oficjalnych odpowiedzi dla tej pozycji.'
                : 'No official answers for this position yet.'}
            </p>
          ) : (
            <ul>
              {current.map((r) => (
                <li
                  key={r.player_slug}
                  className="border-b px-5 py-5 last:border-b-0"
                  style={{ borderColor: 'var(--line-soft)' }}
                >
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="min-w-0 flex-1 break-words text-[15px] font-medium">{r.player}</span>
                    <RarityIndicator percent={r.pick_percent} locale={locale} className="ml-auto text-right text-sm" />
                  </div>
                  <div className="mt-3 h-[3px]" style={{ background: 'var(--line-soft)' }}>
                    <div
                      style={{
                        width: `${Math.max(1, Math.min(100, r.pick_percent))}%`,
                        height: '100%',
                        background: rarityColor[rarityForPercent(r.pick_percent) ?? 'common'],
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        </section>
        <DailyTop10 dailyId={id} />
        </div>
      </div>
    </GameLayout>
  )
}
