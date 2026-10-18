'use client'
import { useId, useMemo, useState } from 'react'
import { useScoreDistribution } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import LoadError from '@/app/load-error'
import { formatPoints } from '@/lib/points'

const chartWidth = 480
const chartHeight = 180
const chartPadding = 16
const chartBaseline = chartHeight - chartPadding
const scoreX = (score: number) => chartPadding + (1 - Math.max(0, Math.min(500, score)) / 500) * (chartWidth - chartPadding * 2)

function smoothPath(points: { x: number; y: number }[]) {
  if (!points.length) return ''
  let path = `M ${points[0].x} ${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const current = points[i]
    const next = points[i + 1]
    path += ` Q ${current.x} ${current.y} ${(current.x + next.x) / 2} ${(current.y + next.y) / 2}`
  }
  const last = points[points.length - 1]
  return `${path} T ${last.x} ${last.y}`
}

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
  const gradientId = `score-fill-${useId().replace(/:/g, '')}`
  const [bin, setBin] = useState(10)
  const { data, isLoading, isError, refetch } = useScoreDistribution(dailyId, userScore)

  // The API groups scores by rounded points; highlight that same bucket.
  const roundedScore = Math.round(userScore)

  const bars = useMemo(() => {
    const raw: { score: number; count: number }[] = (data?.distribution || []).filter(
      (entry: { score: number; count: number }) => Number.isFinite(entry.score) && entry.score >= 0 && entry.score <= 500 && entry.count > 0,
    )
    if (!raw.length) return []
    const out: { from: number; to: number; count: number; mine: boolean }[] = []
    for (let x = 0; x <= 500; x += bin) {
      out.push({
        from: x,
        to: Math.min(500, x + bin - 1),
        count: raw.filter((d) => d.score >= x && d.score < x + bin).reduce((s, d) => s + d.count, 0),
        mine: roundedScore >= x && roundedScore < x + bin,
      })
    }
    return out.reverse()
  }, [data?.distribution, bin, roundedScore])

  const curve = useMemo(() => {
    const raw: { score: number; count: number }[] = (data?.distribution || []).filter(
      (entry: { score: number; count: number }) => Number.isFinite(entry.score) && entry.score >= 0 && entry.score <= 500 && entry.count > 0,
    )
    if (!raw.length) return ''
    // A fixed bandwidth softens real score counts without adding submissions.
    const density = Array.from({ length: 101 }, (_, index) => {
      const score = 500 - index * 5
      const count = raw.reduce((sum, entry) => sum + entry.count * Math.exp(-0.5 * ((score - entry.score) / 18) ** 2), 0)
      return { score, count }
    })
    const peak = Math.max(...density.map((point) => point.count))
    return smoothPath(density.map((point) => ({
      x: scoreX(point.score),
      y: chartBaseline - point.count / peak * (chartBaseline - chartPadding - 8),
    })))
  }, [data?.distribution])

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
    const mine = scoreX(userScore)
    return <div>
      {compactMetrics}
      <p className="my-5 text-center text-sm" style={{ color: 'var(--text-dim)' }}>
        {locale === 'pl' ? `Twój wynik jest lepszy niż ${formatPoints(data?.percentile ?? 0, locale)}% wyników.` : `Your score is higher than ${formatPoints(data?.percentile ?? 0, locale)}% of scores.`}
      </p>
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img"
        aria-label={locale === 'pl' ? 'Rozkład wyników z oznaczeniem Twojego wyniku' : 'Score distribution with your score marked'}
        aria-describedby={`${gradientId}-description`} className="w-full">
        <desc id={`${gradientId}-description`}>{locale === 'pl'
          ? `500 po lewej, 0 po prawej. Twój wynik: ${formatPoints(userScore, locale)}.`
          : `500 on the left, 0 on the right. Your score: ${formatPoints(userScore, locale)}.`}</desc>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--gold)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--gold)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((fraction) => <line key={fraction} x1={chartPadding} x2={chartWidth - chartPadding}
          y1={chartPadding + fraction * (chartBaseline - chartPadding)} y2={chartPadding + fraction * (chartBaseline - chartPadding)} stroke="var(--line-soft)" />)}
        <path d={`${curve} L ${chartWidth - chartPadding} ${chartBaseline} L ${chartPadding} ${chartBaseline} Z`} fill={`url(#${gradientId})`} />
        <path d={curve} fill="none" stroke="var(--gold)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <line x1={chartPadding} x2={chartWidth - chartPadding} y1={chartBaseline} y2={chartBaseline} stroke="var(--line)" />
        <line data-user-score={userScore} x1={mine} x2={mine} y1={chartPadding} y2={chartBaseline} stroke="var(--gold)" strokeDasharray="3 5" />
        <rect x={mine - 3.5} y={chartBaseline - 3.5} width="7" height="7" fill="var(--gold)" stroke="white" strokeWidth="1.5" />
      </svg>
      <div data-score-axis className="flex justify-between text-xs tabular" style={{ color: 'var(--text-dim)' }}><span>500</span><span>{locale === 'pl' ? 'Twój wynik' : 'Your score'}: {formatPoints(userScore, locale)}</span><span>0</span></div>
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
        <span>500</span>
        <span>{locale === 'pl' ? 'punkty' : 'points'}</span>
        <span>0</span>
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
    </div>
  )
}
