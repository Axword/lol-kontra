'use client'
import { useQuery } from '@tanstack/react-query'
import { useRef } from 'react'
import { api, Daily } from '@/lib/api'
import CalendarCard from './CalendarCard'

export default function ArchiveList({ currentId }: { currentId?: number }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['dailies', 'archive'],
    queryFn: async () => (await api.get('/dailies/', { params: { ordering: '-date', page_size: 60 } })).data,
  })

  const items: Daily[] = (data?.results || []).filter((d: Daily) => d.id !== currentId)
  const todayStr = new Date().toISOString().slice(0, 10)

  const scroll = (dir: 'left' | 'right') => {
    const el = scrollRef.current
    if (!el) return
    el.scrollBy({ left: dir === 'right' ? 240 : -240, behavior: 'smooth' })
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-[13px] font-semibold text-zinc-300 uppercase tracking-wider">Historia</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => scroll('left')}
            className="w-7 h-7 rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white hover:border-zinc-600 flex items-center justify-center transition text-[13px]"
            aria-label="przewiń w lewo"
          >‹</button>
          <button
            onClick={() => scroll('right')}
            className="w-7 h-7 rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white hover:border-zinc-600 flex items-center justify-center transition text-[13px]"
            aria-label="przewiń w prawo"
          >›</button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex gap-2 overflow-hidden">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="flex-shrink-0 w-[64px] h-[90px] bg-zinc-900/50 border border-zinc-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-zinc-600 text-sm py-6 text-center border border-dashed border-zinc-800 rounded-xl">
          Brak archiwalnych wyzwań
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex gap-2 overflow-x-auto pb-1 scroll-smooth"
          style={{ scrollbarWidth: 'none' }}
        >
          {items.map((d: Daily) => (
            <div key={d.id} className="flex-shrink-0 w-[64px]">
              <CalendarCard
                id={d.id}
                date={d.date}
                status={d.status}
                isToday={d.date === todayStr}
                solved={false}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export { default as CalendarCard } from './CalendarCard'
