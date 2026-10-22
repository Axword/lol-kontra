'use client'
import Link from 'next/link'
import { Suspense,useState } from 'react'
import { useSearchParams } from 'next/navigation'
import GameLayout from '@/components/layout/GameLayout'
import LoadError from '@/app/load-error'
import { usePrefs } from '@/lib/store'
import { useInfinityRanking,type InfinityPeriod } from '@/lib/infinity'
import { infinityPeriods } from '@/components/results/InfinitySummary'
import { guestDisplayName } from '@/lib/locale'

export default function InfinityLeaderboard() {
  return <Suspense><InfinityLeaderboardContent /></Suspense>
}
function InfinityLeaderboardContent() {
  const locale = usePrefs(s=>s.locale)
  const pl = locale === 'pl'
  const [page,setPage] = useState(1)
  const params=useSearchParams()
  const [period,setPeriod]=useState<InfinityPeriod>(()=>infinityPeriods.find(p=>p.id===params.get('period'))?.id||'daily')
  const query = useInfinityRanking(page,period)
  const data = query.data
  return <GameLayout gameMode="infinity"><div className="mx-auto max-w-5xl space-y-6">
    <header className="flex flex-wrap items-baseline justify-between gap-3">
      <h1 className="text-[28px] font-semibold sm:text-[32px]">{pl?'Ranking Infinity':'Infinity leaderboard'}</h1>
      <Link href="/infinity" className="text-sm underline underline-offset-4">{pl?'Zagraj':'Play'}</Link>
    </header>
    <p className="text-sm" style={{color:'var(--text-dim)'}}>{pl?'Najwięcej trafionych zawodników w jednej serii. Liczy się najlepsza seria każdego gracza.':'Most players guessed in one run. Each player appears once with their best run.'}</p>
    <nav aria-label={pl?'Okres rankingu':'Leaderboard period'} className="flex flex-wrap gap-2">
      {infinityPeriods.map(p=><button key={p.id} aria-pressed={period===p.id} className={`btn ${period===p.id?'btn-gold':''}`}
        onClick={()=>{setPeriod(p.id);setPage(1)}}>{pl?p.pl:p.en}</button>)}
    </nav>
    {query.isLoading ? <p role="status">{pl?'Wczytywanie…':'Loading…'}</p>
      : query.isError ? <LoadError onRetry={()=>{void query.refetch()}} />
      : !data?.results.length ? <p className="border bg-[var(--panel)] p-6" style={{borderColor:'var(--line)'}}>{pl?'Brak wyników.':'No results yet.'}</p>
      : <div className="overflow-x-auto border bg-[var(--panel)]" style={{borderColor:'var(--line)'}}><table className="w-full text-sm">
        <thead><tr className="border-b" style={{borderColor:'var(--line)'}}><th className="px-4 py-4 text-left">#</th><th className="px-4 py-4 text-left">{pl?'Gracz':'Player'}</th><th className="px-4 py-4 text-right">{pl?'Trafienia':'Correct guesses'}</th></tr></thead>
        <tbody>{data.results.map(row=><tr key={row.rank} className="border-b last:border-b-0" style={{borderColor:'var(--line-soft)'}}>
          <td className="px-4 py-4 tabular">{row.rank}</td><td className="break-words px-4 py-4">{guestDisplayName(row.nickname,locale)}</td>
          <td className="px-4 py-4 text-right font-semibold tabular" style={{color:'var(--gold)'}}>{row.correct_count}</td>
        </tr>)}</tbody>
      </table></div>}
    {data && data.total_pages>1 && <nav aria-label={pl?'Strony rankingu Infinity':'Infinity leaderboard pages'} className="flex items-center justify-between gap-3 text-sm">
      <button disabled={data.page<=1} onClick={()=>setPage(data.page-1)} className="btn disabled:opacity-40">{pl?'Poprzednia':'Previous'}</button>
      <span className="tabular">{data.page} / {data.total_pages}</span>
      <button disabled={data.page>=data.total_pages} onClick={()=>setPage(data.page+1)} className="btn disabled:opacity-40">{pl?'Następna':'Next'}</button>
    </nav>}
  </div></GameLayout>
}
