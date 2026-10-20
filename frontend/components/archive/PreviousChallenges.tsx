'use client'
import Link from 'next/link'
import { useLayoutEffect, useRef, useState } from 'react'
import { Daily } from '@/lib/api'
import { useChallengeCalendar } from '@/lib/challenge-calendar'
import { isAvailableDaily, useGameDate } from '@/lib/daily'
import { usePrefs } from '@/lib/store'
import { completedDaily, useChallengeProgress } from '@/lib/challenge-progress'
import CalendarCard from './CalendarCard'

export default function PreviousChallenges({ currentId }: { currentId: number }) {
  const locale = usePrefs(s => s.locale)
  const token = usePrefs(s => s.guestToken)
  const today = useGameDate()
  const archive = useChallengeCalendar(today)
  const progress = useChallengeProgress(token)
  const rail = useRef<HTMLDivElement>(null)
  const previousWidth = useRef(0)
  const drag = useRef({ startX: 0, startScroll: 0, pointer: -1, moved: false })
  const [dragging, setDragging] = useState(false)
  const archiveItems: Daily[] = archive.data?.pages.flatMap(page => page.results) || []
  const items = [...archiveItems].filter(d => d.id !== currentId && isAvailableDaily(d, today))
    .sort((a, b) => a.date.localeCompare(b.date))
  const loadOlder = () => { if (archive.hasNextPage && !archive.isFetchingNextPage && !archive.isFetchNextPageError) void archive.fetchNextPage() }
  useLayoutEffect(() => {
    const element = rail.current
    if (!element) return
    const width = element.scrollWidth
    if (!previousWidth.current) element.scrollLeft = width
    else if (width > previousWidth.current) {
      const difference = width - previousWidth.current
      element.scrollLeft += difference
      if (drag.current.pointer !== -1) drag.current.startScroll += difference
    }
    previousWidth.current = width
    if (width <= element.clientWidth) loadOlder()
    // Preserve the visible dates when an older page is prepended.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length, archive.hasNextPage])
  return <section className="border-t pt-7 pb-2" style={{ borderColor: 'var(--line)' }} aria-labelledby="previous-challenges-title">
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 id="previous-challenges-title" className="text-base font-semibold">{locale === 'pl' ? 'Poprzednie wyzwania' : 'Previous challenges'}</h2>
      <Link href="/archiwum" className="text-xs underline underline-offset-4" style={{ color: 'var(--text-dim)' }}>{locale === 'pl' ? 'Wszystkie' : 'View all'}</Link>
    </div>
    {archive.isLoading ? <p role="status" className="text-sm">{locale === 'pl' ? 'Wczytywanie…' : 'Loading…'}</p>
      : archive.isError ? <button className="text-sm underline" onClick={() => { void archive.refetch() }}>{locale === 'pl' ? 'Wczytaj wyzwania ponownie' : 'Retry loading challenges'}</button>
      : !items.length ? <p className="text-sm" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? 'Brak wcześniejszych wyzwań.' : 'No earlier challenges yet.'}</p>
      : <div ref={rail} tabIndex={0} role="group" className={`challenge-rail flex gap-2 overflow-x-auto pb-2 select-none ${dragging ? 'cursor-grabbing' : 'cursor-grab'}`} aria-label={locale === 'pl' ? 'Lista poprzednich wyzwań' : 'Previous challenges list'}
        onScroll={() => {if (rail.current && rail.current.scrollLeft < 180) loadOlder()}}
        onDragStart={event => event.preventDefault()}
        onPointerDown={event => {
          if (event.pointerType !== 'mouse' || event.button !== 0) {drag.current.moved = false;return}
          drag.current = {startX:event.clientX, startScroll:event.currentTarget.scrollLeft, pointer:event.pointerId, moved:false}
        }}
        onPointerMove={event => {
          if (drag.current.pointer !== event.pointerId) return
          const distance = event.clientX - drag.current.startX
          if (!drag.current.moved && Math.abs(distance) < 6) return
          drag.current.moved = true; setDragging(true)
          if (!event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.setPointerCapture(event.pointerId)
          event.preventDefault(); event.currentTarget.scrollLeft = drag.current.startScroll - distance
        }}
        onPointerUp={event => {
          drag.current.pointer = -1; setDragging(false)
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
        }}
        onPointerCancel={() => {drag.current.pointer = -1;setDragging(false)}}
        onClickCapture={event => {if (drag.current.moved && event.detail > 0) {event.preventDefault();event.stopPropagation()}}}>
        {items.map(daily => <CalendarCard compact key={daily.id} id={daily.id} date={daily.date} isToday={daily.date === today}
          completed={progress.isError ? undefined : completedDaily(progress.data, daily.id)} />)}
      </div>}
    {archive.isFetchingNextPage && <p role="status" className="mt-2 text-xs" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? 'Wczytywanie starszych wyzwań…' : 'Loading older challenges…'}</p>}
    {archive.isFetchNextPageError && <button className="mt-2 text-xs underline" onClick={() => {void archive.fetchNextPage()}}>{locale === 'pl' ? 'Wczytaj starsze wyzwania ponownie' : 'Retry loading older challenges'}</button>}
    {progress.isError && <button className="mt-2 text-xs underline" onClick={() => { void progress.refetch() }}>{locale === 'pl' ? 'Wczytaj statusy ponownie' : 'Retry loading completion'}</button>}
  </section>
}
