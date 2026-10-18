'use client'
import { useMemo, useState } from 'react'
import { useScoreDistribution } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import LoadError from '@/app/load-error'
import { formatPoints } from '@/lib/points'

/**
 * Rozkład wyników wszystkich graczy danego dnia.
 *
 * Poprzednia wersja przy braku danych rysowała wymyślony histogram i podpisywała go
 * "dane demo". Teraz: albo są prawdziwe dane, albo komunikat. Żadnych liczb z sufitu.
 */
export default function ScoreDistribution({
  dailyId,
  userScore,
  practice = false,
  compact = false,
}: {
  dailyId: number
  userScore: number
  practice?: boolean
  compact?: boolean
}) {
  const locale = usePrefs((s) => s.locale)
  const [bin, setBin] = useState(10)
  const { data, isLoading, isError, refetch } = useScoreDistribution(dailyId, userScore)

  // The API groups scores by rounded points; highlight that same bucket.
  const roundedScore = Math.round(userScore)

  const bars = useMemo(() => {
    const raw: { score: number; count: number }[] = data?.distribution || []
    if (!raw.length) return []
    const min = Math.min(...raw.map((d) => d.score), roundedScore, 0)
    const max = Math.max(...raw.map((d) => d.score), roundedScore, 500)
    const start = Math.floor(min / bin) * bin
    const end = Math.ceil((max + 1) / bin) * bin
    const out: { from: number; to: number; count: number; mine: boolean }[] = []
    for (let x = start; x < end; x += bin) {
      out.push({
        from: x,
        to: Math.min(500, x + bin - 1),
        count: raw.filter((d) => d.score >= x && d.score < x + bin).reduce((s, d) => s + d.count, 0),
        mine: roundedScore >= x && roundedScore < x + bin,
      })
    }
    return out
  }, [data?.distribution, bin, roundedScore])

  const maxCount = Math.max(1, ...bars.map((b) => b.count))
  const total = data?.total_submissions ?? 0

  const compactMetrics = (<dl className="grid grid-cols-2 gap-3">
        <div className="border p-4 text-center" style={{ borderColor: 'var(--line)' }}>
          <dt className="text-xs" style={{ color: 'var(--text-dim)' }}>{locale === 'pl' ? 'Końcowy wynik' : 'Final score'}</dt>
          <dd className="mt-2 text-3xl font-semibold tabular">{formatPoints(userScore, locale)}</dd>
        </div>
        <div className="border p-4 text-center" style={{ borderColor: 'var(--line)' }}>
          <dt className="text-xs" style={{ color: 'var(--text-dim)' }}>{locale === 'pl' ? 'Percentyl' : 'Percentile'}</dt>
          <dd className="mt-2 text-3xl font-semibold tabular">{data?.percentile != null ? `${formatPoints(data.percentile, locale)}%` : '—'}</dd>
        </div>
      </dl>)

  if (isLoading) {
    return (
      <div>{compact && compactMetrics}<p role="status" className="p-6 text-sm" style={{ color: 'var(--text-dim)' }}>
        {locale === 'pl' ? 'Liczę rozkład wyników…' : 'Computing the distribution…'}
      </p></div>
    )
  }

  if (isError) return <div>{compact && compactMetrics}<LoadError title={locale === 'pl' ? 'Nie udało się wczytać rozkładu wyników' : 'Could not load score distribution'} onRetry={() => { void refetch() }} /></div>

  if (!bars.length) {
    return (
      <div className="border bg-white p-6" style={{ borderColor: 'var(--line)' }}>
        {compact && compactMetrics}
        <h3 className="mb-2 text-base font-semibold">{locale === 'pl' ? 'Rozkład wyników' : 'Score distribution'}</h3>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
          {locale === 'pl'
            ? 'Nie ma jeszcze rozkładu wyników tej planszy. Pojawi się po przeliczeniu punktów.'
            : 'This board’s score distribution will appear after scores are finalised.'}
        </p>
      </div>
    )
  }

  if (compact) {
    const width = 480, height = 170, padding = 12
    const x = (value: number) => padding + Math.max(0, Math.min(500, value)) / 500 * (width - padding * 2)
    const y = (count: number) => height - padding - count / maxCount * (height - padding * 3)
    const line = bars.map((bar) => `${x((bar.from + bar.to) / 2)},${y(bar.count)}`).join(' ')
    const mine = x(userScore)
    return <div>
      {compactMetrics}
      <p className="my-5 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
        {locale === 'pl' ? `Twój wynik jest lepszy niż ${formatPoints(data?.percentile ?? 0, locale)}% wyników.` : `Your score is higher than ${formatPoints(data?.percentile ?? 0, locale)}% of scores.`}
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={locale === 'pl' ? 'Rozkład wyników z oznaczeniem Twojego wyniku' : 'Score distribution with your score marked'} className="w-full">
        <polyline points={`${padding},${y(0)} ${line} ${width-padding},${y(0)}`} fill="none" stroke="var(--gold)" strokeWidth="2.5" />
        <line x1={mine} x2={mine} y1={padding} y2={y(0)} stroke="var(--gold)" strokeDasharray="4 4" />
        <rect x={mine-3} y={y(0)-3} width="6" height="6" fill="var(--gold)" />
      </svg>
      <div className="flex justify-between text-xs tabular" style={{ color: 'var(--text-dim)' }}><span>0</span><span>{locale === 'pl' ? 'Twój wynik' : 'Your score'}: {formatPoints(userScore, locale)}</span><span>500</span></div>
      {!!data?.seeded_count && <p className="mt-4 text-center text-xs" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? `Próba zawiera ${data.seeded_count} rozgrywek testowych.` : `The sample includes ${data.seeded_count} test games.`}</p>}
    </div>
  }

  return (
    <div className="min-w-0 border bg-white p-6 sm:p-8" style={{ borderColor: 'var(--line)' }}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h3 className="text-base font-semibold">{locale === 'pl' ? 'Rozkład wyników' : 'Score distribution'}</h3>
        <div className="flex items-center gap-1">
          <span className="mr-2 text-xs" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl' ? 'przedział' : 'bin'}
          </span>
          {[5, 10, 25, 50].map((b) => (
            <button
              key={b}
              aria-pressed={bin === b}
              onClick={() => setBin(b)}
              className="min-h-9 min-w-9 border px-2 py-2 text-xs transition-colors tabular"
              style={
                bin === b
                  ? { borderColor: 'var(--gold)', color: 'var(--gold)', background: '#eef5ef' }
                  : { borderColor: 'var(--line)', color: 'var(--text-dim)' }
              }
            >
              {b}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
      <div className="flex h-[160px] items-end gap-[2px] border-b" style={{ borderColor: 'var(--line)', minWidth: bars.length * 6 }}>
        {bars.map((b, i) => (
          <div key={i} title={`${b.from}–${b.to}: ${b.count}`} className="group relative flex min-w-[4px] flex-1 flex-col items-center justify-end">
            <div
              className="w-full"
              style={{
                height: `${Math.max(b.count ? 3 : 1, (b.count / maxCount) * 120)}px`,
                background: b.mine ? 'var(--gold)' : b.count ? '#aabeb0' : 'var(--line-soft)',
              }}
            />
            <span
              className="absolute -top-5 whitespace-nowrap text-[11px] opacity-0 transition-opacity group-hover:opacity-100 tabular"
              style={{ color: 'var(--text-dim)' }}
            >
              {b.from}–{b.to}: {b.count}
            </span>
          </div>
        ))}
      </div>
      </div>

      <div className="mt-2 flex justify-between text-xs tabular" style={{ color: 'var(--text-dim)' }}>
        <span>{bars[0].from}</span>
        <span>{locale === 'pl' ? 'punkty' : 'points'}</span>
        <span>{bars[bars.length - 1].to}</span>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-5 gap-y-6 border-t pt-6 sm:grid-cols-4" style={{ borderColor: 'var(--line-soft)' }}>
        {[
          { k: locale === 'pl' ? 'Twój wynik' : 'Your score', v: formatPoints(userScore, locale), gold: true },
          { k: practice ? (locale === 'pl' ? 'Pozycja porównawcza' : 'Comparative position') : (locale === 'pl' ? 'Miejsce' : 'Rank'), v: data?.rank ? (practice ? data.rank : `${data.rank} / ${total}`) : '—' },
          { k: locale === 'pl' ? 'Lepszy niż' : 'Better than', v: data?.percentile != null ? `${data.percentile}%` : '—' },
          { k: locale === 'pl' ? 'Średnia' : 'Average', v: data?.avg_score != null ? Math.round(data.avg_score) : '—' },
        ].map((s) => (
          <div key={s.k}>
            <dt className="text-xs" style={{ color: 'var(--text-dim)' }}>{s.k}</dt>
            <dd className="mt-2 text-xl font-semibold tabular" style={{ color: s.gold ? 'var(--gold)' : 'var(--text)' }}>
              {s.v}
            </dd>
          </div>
        ))}
      </dl>
      {!!data?.seeded_count && <p className="mt-5 text-xs" style={{ color: 'var(--text-faint)' }}>
        {locale === 'pl' ? `Próba zawiera ${data.seeded_count} rozgrywek testowych.` : `The sample includes ${data.seeded_count} test games.`}
      </p>}
    </div>
  )
}
