'use client'
import { Daily } from '@/lib/api'
import { useChallengeCalendar } from '@/lib/challenge-calendar'
import { usePrefs } from '@/lib/store'
import CalendarCard from './CalendarCard'
import { isAvailableDaily, useGameDate } from '@/lib/daily'
import LoadError from '@/app/load-error'
import { completedDaily, useChallengeProgress } from '@/lib/challenge-progress'

export default function ArchiveList() {
  const locale = usePrefs((s) => s.locale)
  const token = usePrefs((s) => s.guestToken)
  const progress = useChallengeProgress(token)
  const today = useGameDate()
  const { data, isLoading, isError, refetch, hasNextPage, fetchNextPage, isFetchingNextPage, isFetchNextPageError } = useChallengeCalendar(today)
  const items: Daily[] = (data?.pages.flatMap(page => page.results) || []).filter((daily: Daily) => isAvailableDaily(daily, today))

  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7" aria-hidden="true">
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} className="h-[132px] border bg-[var(--panel)]" style={{ borderColor: 'var(--line)', opacity: 0.5 }} />
        ))}
      </div>
    )
  }

  if (isError) return <LoadError onRetry={() => { void refetch() }} />

  if (items.length === 0) {
    return (
      <p className="border bg-[var(--panel)] px-6 py-12 text-center text-sm" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
        {locale === 'pl' ? 'Brak archiwalnych plansz.' : 'No archived boards yet.'}
      </p>
    )
  }

  return (
    <><div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
      {items.map((d) => (
        <CalendarCard key={d.id} id={d.id} date={d.date} isToday={d.date === today} completed={progress.isError ? undefined : completedDaily(progress.data, d.id)} />
      ))}
    </div>
    {hasNextPage && <div className="mt-6 text-center"><button disabled={isFetchingNextPage} onClick={() => {void fetchNextPage()}}
      className="btn disabled:opacity-50">{isFetchingNextPage ? (locale === 'pl' ? 'Wczytywanie…' : 'Loading…')
        : isFetchNextPageError ? (locale === 'pl' ? 'Spróbuj ponownie' : 'Try again') : (locale === 'pl' ? 'Pokaż starsze wyzwania' : 'Show older challenges')}</button></div>}</>
  )
}
