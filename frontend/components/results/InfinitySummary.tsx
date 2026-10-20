'use client'
import Link from 'next/link'
import { useId,useRef,useState } from 'react'
import type { InfinityPeriod,InfinityRun } from '@/lib/infinity'
import { usePrefs } from '@/lib/store'
import { useDialog } from '../ui/useDialog'

export const infinityPeriods:{id:InfinityPeriod;pl:string;en:string}[]=[
  {id:'daily',pl:'Dzienny',en:'Daily'},
  {id:'weekly',pl:'Tygodniowy',en:'Weekly'},
  {id:'monthly',pl:'Miesięczny',en:'Monthly'},
  {id:'all_time',pl:'Historyczny',en:'All-time'},
]

export default function InfinitySummary({run,onRestart,pending,error}:{run:InfinityRun;onRestart:()=>void;pending:boolean;error:boolean}) {
  const pl=usePrefs(s=>s.locale)==='pl'
  const [open,setOpen]=useState(true)
  const titleId=useId()
  const resultButton=useRef<HTMLButtonElement>(null)
  const dialog=useDialog<HTMLDivElement>(open,()=>setOpen(false),resultButton)
  return <>
    <div className="flex justify-center"><button ref={resultButton} className="btn" onClick={()=>setOpen(true)}>{pl?'Twój wynik':'Your result'}</button></div>
    {open&&<div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <div className="picker-backdrop absolute inset-0" onClick={()=>setOpen(false)} />
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className="panel relative max-h-[calc(100dvh-24px)] w-full max-w-lg overflow-y-auto p-5 sm:p-7 scroll-thin">
        <div className="mb-6 flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-xl font-semibold">{pl?'Seria zakończona':'Run finished'}</h2>
          <button onClick={()=>setOpen(false)} aria-label={pl?'Zamknij':'Close'} className="h-8 w-8 shrink-0 text-2xl leading-none">×</button>
        </div>
        <div className="mb-6 text-center">
          <p className="text-sm" style={{color:'var(--text-dim)'}}>{pl?'Poprawnie odgadnięci zawodnicy':'Correctly guessed players'}</p>
          <p className="mt-2 text-5xl font-semibold tabular" style={{color:'var(--gold)'}}>{run.correct_count}</p>
        </div>
        <ul className="divide-y border-y" style={{borderColor:'var(--line)'}}>
          {infinityPeriods.map(period=>{
            const result=run.ranking_result?.periods[period.id]
            return <li key={period.id} className="flex items-center justify-between gap-4 py-3">
              <Link href={`/infinity/leaderboard?period=${period.id}`} className="text-sm underline-offset-4 hover:underline">{pl?period.pl:period.en}</Link>
              <span className="text-right">
                <span className="block text-lg font-semibold tabular">{result?.rank!=null?`#${result.rank}`:'—'}</span>
                {result?.improved&&result.previous_rank!=null&&<span className="block text-xs tabular" style={{color:'var(--gold)'}}>
                  {pl?`Awans z #${result.previous_rank} na #${result.rank}`:`Up from #${result.previous_rank} to #${result.rank}`}
                </span>}
              </span>
            </li>
          })}
        </ul>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <button className="btn btn-gold disabled:opacity-50" disabled={pending} onClick={onRestart}>{pending?(pl?'Losowanie…':'Drawing…'):(pl?'Zagraj ponownie':'Play again')}</button>
          <Link href="/infinity/leaderboard" className="btn">{pl?'Ranking Infinity':'Infinity leaderboard'}</Link>
        </div>
        {error&&<p role="alert" className="mt-4 text-sm" style={{color:'var(--bad)'}}>{pl?'Nie udało się rozpocząć serii. Spróbuj ponownie.':'Could not start a run. Try again.'}</p>}
      </div>
    </div>}
  </>
}
