'use client'
import { useArchive } from '@/lib/api'
import { useGameStore } from '@/lib/store'
import CalendarCard from './CalendarCard'

export default function ArchiveList({ currentId }: { currentId?: number }) {
  const { data, isLoading } = useArchive()
  const games = useGameStore(s => s.games)

  const items = (data || []).filter(d => d.id !== currentId)
  const todayStr = new Date().toISOString().slice(0, 10)

  return (
    <div className="mt-2">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h3 className="text-[15px] font-bold text-ink">Poprzednie wyzwania</h3>
        <div className="text-[11px] text-muted">kliknij kartkę z kalendarza aby zagrać</div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-3">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="h-[150px] bg-surface border border-line rounded-console animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-3 sm:gap-4">
          {items.slice(0, 28).map(d => {
            const g = games[d.id]
            return (
              <CalendarCard
                key={d.id}
                id={d.id}
                date={d.date}
                isToday={d.date === todayStr}
                solved={!!g?.finished}
                score={g?.score ?? null}
              />
            )
          })}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="text-muted text-sm py-8 text-center border border-dashed border-line rounded-console">
          Brak archiwalnych Daily – to pierwszy dzień!
        </div>
      )}

      <div className="text-[10px] text-muted mt-3 px-1">
        Każda kartka = 1 Daily • 5 ról • kliknij by zagrać historyczne wyzwanie • wynik instant
      </div>
    </div>
  )
}

// re-export CalendarCard for direct use if needed
export { default as CalendarCard } from './CalendarCard'
