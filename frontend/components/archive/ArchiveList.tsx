'use client'
import { useQuery } from '@tanstack/react-query'
import { api, Daily } from '@/lib/api'
import CalendarCard from './CalendarCard'

export default function ArchiveList({ currentId }: { currentId?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['dailies','archive'],
    queryFn: async () => (await api.get('/dailies/', { params: { ordering: '-date', page_size: 42 } })).data,
  })

  const items: Daily[] = (data?.results || []).filter((d:Daily) => d.id !== currentId)
  const todayStr = new Date().toISOString().slice(0,10)

  return (
    <div className="mt-2">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h3 className="text-[15px] font-bold text-zinc-200">Poprzednie wyzwania</h3>
        <div className="text-[11px] text-zinc-500">kliknij kartkę z kalendarza aby zagrać</div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-3">
          {Array.from({length:14}).map((_,i)=>(
            <div key={i} className="h-[150px] bg-zinc-900/50 border border-zinc-800 rounded-[14px] animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-3 sm:gap-4">
          {items.slice(0,28).map((d:Daily) => (
            <CalendarCard
              key={d.id}
              id={d.id}
              date={d.date}
              status={d.status}
              isToday={d.date === todayStr}
              solved={false}
            />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="text-zinc-500 text-sm py-8 text-center border border-dashed border-zinc-800 rounded-xl">
          Brak archiwalnych Daily – to pierwszy dzień!<br/>
          <span className="text-[11px]">Uruchom: <code>python manage.py seed_history --days 30</code></span>
        </div>
      )}

      <div className="text-[10px] text-zinc-500 mt-3 px-1">
        Każda kartka = 1 Daily • 5 ról • kliknij by zagrać historyczne wyzwanie • wynik instant
      </div>
    </div>
  )
}

// re-export CalendarCard for direct use if needed
export { default as CalendarCard } from './CalendarCard'

