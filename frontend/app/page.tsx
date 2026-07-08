'use client'
import { useDailyToday } from '@/lib/api'
import RosterBoard from '@/components/roster/RosterBoard'
import GameLayout from '@/components/layout/GameLayout'
import ResultsChart from '@/components/results/ResultsChart'
import DailyTop10 from '@/components/leaderboard/DailyTop10'
import ArchiveList from '@/components/archive/ArchiveList'
import { useRosterStore } from '@/lib/store'
import { useState, useEffect } from 'react'
import { sound } from '@/lib/sound'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export default function HomePage() {
  const { data, isLoading, error, refetch } = useDailyToday()
  const picks = useRosterStore(s => s.picks)
  const submitted = useRosterStore(s => s.submitted)
  const guestToken = useRosterStore(s => s.guestToken)
  const [locale, setLocale] = useState<'pl'|'en'>('pl')
  const [errorsUsed, setErrorsUsed] = useState(0) // UI only – 10 lives
  // try to get last submission score – in real app fetch /submissions/me
  const [lastScore, setLastScore] = useState<number | null>(null)

  // fetch my submission result – instant mode
  const mySubmission = useQuery({
    queryKey: ['my-submission', data?.id, submitted],
    queryFn: async () => {
      if (!data?.id) return null
      try {
        const r = await api.get('/submissions/me/', { params: { daily_id: data.id, guest_token: guestToken } })
        return r.data
      } catch { return null }
    },
    enabled: !!submitted && !!data?.id,
    refetchInterval: submitted ? 5000 : false,
  })

  useEffect(() => {
    if (mySubmission.data?.total_points !== undefined) {
      setLastScore(mySubmission.data.total_points)
      if (mySubmission.data.total_points > 0) {
        // update errorsUsed roughly – assume 0 errors if perfect, else some
        setErrorsUsed(Math.max(0, 5 - (mySubmission.data.answers?.filter((a:any)=>a.is_correct).length || 0)))
      }
    }
  }, [mySubmission.data])

  // listen to submit success via store? simple: poll
  // for demo: if submitted, show mock score 127
  const userScore = lastScore ?? (submitted ? 127 : 0)

  if (isLoading) return (
    <GameLayout locale={locale} onLocaleChange={(l)=>setLocale(l as any)} errorsLeft={10-errorsUsed}>
      <div className="text-center py-24 text-zinc-400">Ładowanie Daily…</div>
    </GameLayout>
  )
  if (error || !data) return (
    <GameLayout locale={locale} onLocaleChange={(l)=>setLocale(l as any)} errorsLeft={10-errorsUsed}>
      <div className="text-center py-20 text-red-400">
        Błąd ładowania Daily.<br/>
        <span className="text-sm text-zinc-400">Sprawdź czy API działa: http://localhost:8000/api/v1/dailies/today/</span><br/>
        <button onClick={()=>refetch()} className="mt-3 pill">Spróbuj ponownie</button>
      </div>
    </GameLayout>
  )

  const filled = data.slots.filter((s:any)=> picks[s.id]?.playerSlug).length

  // left top slot – score
  const leftTop = (
    <div className="flex items-baseline gap-3">
      <div>
        <div className="text-[11px] text-zinc-400 uppercase tracking-wider">Daily #{data.id}</div>
        <div className="text-[15px] font-bold text-white">
          Wynik: <span className="text-[#C89B3C]">{submitted ? `${userScore} pkt` : '—'}</span>
          <span className="text-zinc-500 font-normal text-[12px] ml-2">{data.date}</span>
        </div>
      </div>
      <div className="hidden sm:block text-[11px] text-zinc-400">
        Tryb: {data.reveal_mode === 'instant' ? 'Na żywo' : 'Po zamknięciu'}
      </div>
    </div>
  )

  const rightTop = (
    <div className="text-right">
      <div className="text-[11px] text-zinc-400">Wypełniono</div>
      <div className="text-[15px] font-bold">{filled}<span className="text-zinc-500">/5</span></div>
    </div>
  )

  return (
    <GameLayout
      locale={locale}
      onLocaleChange={(l)=>setLocale(l as any)}
      leftTopSlot={leftTop}
      rightTopSlot={rightTop}
      errorsLeft={Math.max(0, 10 - errorsUsed)}
    >
      <div className="space-y-6">
        {/* Game board */}
        <RosterBoard daily={data} onScore={(total, answers)=>{
          setLastScore(total)
          // update errors used – count incorrect answers
          const wrong = answers?.filter((a:any)=>!a.is_correct).length || 0
          setErrorsUsed(Math.min(10, wrong))
          // play final sound
          if (total > 100) { import('@/lib/sound').then(m=>m.sound.success()) }
        }} />

        {/* info under map */}
        <div className="text-center text-[13px] text-zinc-400 -mt-2">
          {submitted
            ? '✅ Skład wysłany – wynik poniżej'
            : '👆 Wybierz pozycje na mapie by zgadywać'}
        </div>

        {/* Results – show after submit */}
        {submitted && (
          <div className="space-y-4 animate-in fade-in">
            <ResultsChart dailyId={data.id} userScore={userScore} totalPlayers={1247} />
            <div className="grid md:grid-cols-3 gap-3 text-[12px]">
              {[
                {k:'Poprawne',v:'5/5',c:'text-emerald-400'},
                {k:'Legendary',v:'1',c:'text-[#F59E0B]'},
                {k:'Diamond',v:'0',c:'text-[#22D3EE]'},
              ].map(x=>(
                <div key={x.k} className="bg-[#0f141b] border border-zinc-800 rounded-xl px-3 py-2 text-center">
                  <div className="text-zinc-400 text-[11px]">{x.k}</div>
                  <div className={`text-lg font-bold ${x.c}`}>{x.v}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top 10 + stats */}
        <div className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <DailyTop10 dailyId={data.id} />
          </div>
          <div className="space-y-3">
            <div className="card-lol">
              <div className="text-[11px] text-zinc-400 uppercase mb-1">Twoje staty</div>
              <div className="text-sm space-y-1 text-zinc-300">
                <div>Średni wynik: <b>—</b></div>
                <div>Najlepszy: <b className="text-[#C89B3C]">—</b></div>
                <div>Streak: <b>0</b> 🔥</div>
                <div>Diamond Picks: <b className="text-[#22D3EE]">0 💎</b></div>
              </div>
              <a href="/profile" className="text-[11px] text-[#C89B3C] hover:underline mt-2 inline-block">zaloguj by zapisać →</a>
            </div>
            <div className="card-lol text-[11px] text-zinc-400 leading-relaxed">
              <b className="text-zinc-200">Tip:</b> Rzadkie picki = więcej punktów.<br/>
              Sprawdź historię drużyn, trenerów, lata Worlds – tam są ukryte perełki.
            </div>
          </div>
        </div>

        {/* Archive */}
        <ArchiveList currentId={data.id} />
      </div>
    </GameLayout>
  )
}
