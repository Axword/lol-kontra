'use client'
import { Daily, useArchive } from '@/lib/api'
import { usePrefs } from '@/lib/store'
import CalendarCard from './CalendarCard'
import { isAvailableDaily, useGameDate } from '@/lib/daily'
import LoadError from '@/app/load-error'

export default function ArchiveList() {
  const locale = usePrefs((s) => s.locale)
  const { data, isLoading, isError, refetch } = useArchive()
  const today = useGameDate()
  const items: Daily[] = (data?.results || []).filter((daily: Daily) => isAvailableDaily(daily, today))

  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7" aria-hidden="true">
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={i} className="h-[132px] border bg-white" style={{ borderColor: 'var(--line)', opacity: 0.5 }} />
        ))}
      </div>
    )
  }

  if (isError) return <LoadError onRetry={() => { void refetch() }} />

  if (items.length === 0) {
    return (
      <p className="border bg-white px-6 py-12 text-center text-sm" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
        {locale === 'pl' ? 'Brak archiwalnych plansz.' : 'No archived boards yet.'}
      </p>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
      {items.map((d) => (
        <CalendarCard key={d.id} id={d.id} date={d.date} isToday={d.date === today} />
      ))}
    </div>
  )
}
