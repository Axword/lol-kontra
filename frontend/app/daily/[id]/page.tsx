'use client'
import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api, Daily } from '@/lib/api'
import GameLayout from '@/components/layout/GameLayout'
import RosterBoard from '@/components/roster/RosterBoard'
import { useRosterStore } from '@/lib/store'
import { useState, useEffect } from 'react'
import Link from 'next/link'

export default function DailyIdPage() {
  const params = useParams()
  const router = useRouter()
  const id = params?.id as string
  const [locale, setLocale] = useState<'pl'|'en'>('pl')

  const { data, isLoading, error } = useQuery<Daily>({
    queryKey: ['daily', id],
    queryFn: async () => (await api.get(`/dailies/${id}/`)).data,
    enabled: !!id,
  })

  // if already submitted, offer go to results
  const submitted = useRosterStore(s => s.submitted)
  const picks = useRosterStore(s => s.picks)

  const filled = data ? data.slots.filter((s:any)=>picks[s.id]?.playerSlug).length : 0

  const leftTop = data ? (
    <div className="flex items-baseline gap-3">
      <button onClick={()=>router.push('/')} className="text-zinc-400 hover:text-white text-[12px]">← Daily list</button>
      <div>
        <div className="text-[11px] text-zinc-400 uppercase">Daily #{data.id}</div>
        <div className="text-[15px] font-bold text-white">{data.date} <span className="text-zinc-400 text-[12px] font-normal">• {data.status}</span></div>
      </div>
    </div>
  ) : null

  const rightTop = data ? (
    <div className="text-right">
      <div className="text-[11px] text-zinc-400">Wypełniono</div>
      <div className="text-[15px] font-bold">{filled}<span className="text-zinc-500">/5</span></div>
    </div>
  ) : null

  return (
    <GameLayout
      locale={locale}
      onLocaleChange={(l)=>setLocale(l as any)}
      leftTopSlot={leftTop}
      rightTopSlot={rightTop}
      errorsLeft={10}
    >
      {!id || isLoading ? (
        <div className="text-center py-24 text-zinc-400">Ładowanie Daily #{id}…</div>
      ) : error || !data ? (
        <div className="text-center py-20">
          <div className="text-red-400 mb-2">Nie znaleziono Daily #{id}</div>
          <Link href="/" className="text-[#C89B3C] hover:underline text-sm">Wróć do dzisiejszego →</Link>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex items-center justify-between text-[12px] text-zinc-400 px-1">
            <span>Archiwalne wyzwanie – możesz zagrać 1 raz (osobny zapis niż Daily Today)</span>
            <Link href={`/results/${data.id}`} className="text-[#C89B3C] hover:underline">Zobacz wyniki →</Link>
          </div>
          <RosterBoard daily={data} />
          <div className="text-center text-[12px] text-zinc-500">
            To jest Daily #{data.id} z dnia {data.date} – tryb: <b className="text-zinc-300">{data.reveal_mode}</b>
            {' '}• <Link href={`/results/${data.id}`} className="text-[#C89B3C] hover:underline">przejdź do wyników</Link>
          </div>
        </div>
      )}
    </GameLayout>
  )
}
