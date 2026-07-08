'use client'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import GameLayout from '@/components/layout/GameLayout'
import { useState, useMemo } from 'react'
import { countryFlag } from '@/lib/flags'
import Link from 'next/link'

type AnswerStat = {
  slot_id: number,
  slot_role: string,
  player: string,
  player_slug: string,
  pick_percent: number,
  rarity_tier: string,
  pick_count?: number
}

export default function ResultsPage() {
  const params = useParams()
  const id = params?.id as string
  const [selectedRole, setSelectedRole] = useState<string | null>(null)
  const [locale, setLocale] = useState<'pl'|'en'>('pl')

  // daily meta
  const dailyQ = useQuery({
    queryKey: ['daily', id],
    queryFn: async () => (await api.get(`/dailies/${id}/`)).data,
    enabled: !!id
  })
  // my submission
  const mySubQ = useQuery({
    queryKey: ['my-submission-result', id],
    queryFn: async () => {
      try {
        // try guest_token from localStorage
        const guest = typeof window !== 'undefined' ? localStorage.getItem('guest_token') || '' : ''
        const r = await api.get('/submissions/me/', { params: { daily_id: id, guest_token: guest }})
        return r.data
      } catch { return null }
    },
    enabled: !!id,
    refetchInterval: 8000
  })

  // answer stats – percentage only in UI
  const statsQ = useQuery({
    queryKey: ['answer-stats', id],
    queryFn: async () => (await api.get(`/dailies/${id}/answer-stats/`)).data,
    enabled: !!id,
    refetchInterval: 15000
  })

  const daily = dailyQ.data
  const mySub = mySubQ.data
  const stats: AnswerStat[] = statsQ.data?.results || []

  // group stats by role
  const statsByRole = useMemo(() => {
    const map: Record<string, AnswerStat[]> = {}
    stats.forEach(s => {
      if (!map[s.slot_role]) map[s.slot_role] = []
      map[s.slot_role].push(s)
    })
    // sort by percent desc
    Object.keys(map).forEach(k => {
      map[k].sort((a,b) => b.pick_percent - a.pick_percent)
    })
    return map
  }, [stats])

  const roles: Array<'top'|'jungle'|'mid'|'adc'|'support'> = ['top','jungle','mid','adc','support']
  const roleLabels: Record<string,string> = {top:'TOP', jungle:'JNG', mid:'MID', adc:'ADC', support:'SUP'}

  // auto-select first role with data, or first slot
  const activeRole = selectedRole || (daily?.slots?.[0]?.role) || 'mid'
  const activeStats = statsByRole[activeRole] || []

  // my pick per role
  const myPickByRole: Record<string, any> = {}
  if (mySub?.answers) {
    mySub.answers.forEach((a:any) => {
      myPickByResult: myPickByRole[a.slot_role] = a
    })
  }

  const totalPoints = mySub?.total_points ?? null

  return (
    <GameLayout
      locale={locale}
      onLocaleChange={(l)=>setLocale(l as any)}
      leftTopSlot={
        daily ? (
          <div>
            <div className="text-[11px] text-zinc-400 uppercase">Wyniki – Daily #{daily.id}</div>
            <div className="text-[15px] font-bold text-white">
              {daily.date} 
              <span className="ml-2 text-[#C89B3C]">{totalPoints !== null ? `${totalPoints} pkt` : '—'}</span>
            </div>
          </div>
        ) : null
      }
      rightTopSlot={
        <Link href={daily ? `/daily/${daily.id}` : '/'} className="text-[12px] text-[#C89B3C] hover:underline">
          ← wróć do gry
        </Link>
      }
      errorsLeft={10}
    >
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-[18px] sm:text-[20px] font-bold">Rezultaty – {daily ? `Daily #${daily.id}` : ''}</h1>
          <div className="text-[11px] text-zinc-400">kliknij rolę aby zobaczyć statystyki %</div>
        </div>

        {/* main 2-col: left roster, right stats */}
        <div className="grid lg:grid-cols-5 gap-4">
          {/* left – your roster */}
          <div className="lg:col-span-2 space-y-2">
            <div className="text-[11px] text-zinc-400 uppercase tracking-wider px-1">Twój skład</div>
            {roles.map(role => {
              const slot = daily?.slots?.find((s:any)=>s.role===role)
              const pick = myPickByRole[role]
              const isActive = activeRole === role
              return (
                <button
                  key={role}
                  onClick={()=>setSelectedRole(role)}
                  className={`w-full text-left rounded-2xl border px-3 py-3 transition flex items-center gap-3
                    ${isActive 
                      ? 'border-[#C89B3C] bg-[#141a22] shadow-[0_0_14px_rgba(200,155,60,0.18)]' 
                      : 'border-zinc-800 bg-[#0f141b] hover:border-zinc-700'
                    }`}
                >
                  <img src={`/roles/${role}.svg`} alt={role} className="w-9 h-9 opacity-90" style={{filter: pick ? 'brightness(1.15) sepia(.2)' : 'grayscale(1) brightness(.7)'}} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-[#C8AC6E] uppercase tracking-wider">{roleLabels[role]}</div>
                    <div className="font-semibold truncate text-[14px]">
                      {pick ? pick.player_nickname : <span className="text-zinc-500">— brak —</span>}
                    </div>
                    {pick && (
                      <div className="text-[11px] mt-0.5">
                        {pick.is_correct ? (
                          <span className={
                            pick.rarity_tier==='legendary' ? 'text-[#F59E0B] font-bold' :
                            pick.rarity_tier==='epic' ? 'text-[#A855F7]' :
                            pick.rarity_tier==='rare' ? 'text-[#3B82F6]' : 'text-zinc-300'
                          }>
                            {pick.rarity_tier || 'common'} • {pick.rarity_percent ? `${Number(pick.rarity_percent).toFixed(1)}%` : ''} • {pick.points_awarded} pkt
                            {pick.is_diamond_pick && ' 💎'}
                          </span>
                        ) : (
                          <span className="text-red-400">błędna odpowiedź – 0 pkt</span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="text-zinc-500">›</div>
                </button>
              )
            })}
            {!mySub && (
              <div className="text-[12px] text-zinc-400 bg-zinc-950 border border-zinc-900 rounded-xl p-3">
                Nie znaleźliśmy Twojego zgłoszenia dla tego Daily (guest_token).<br/>
                Jeśli grałeś – upewnij się że masz ten sam browser / localStorage.<br/>
                Poniżej i tak zobaczysz globalne statystyki % społeczności.
              </div>
            )}
          </div>

          {/* right – stats per role – PERCENT ONLY */}
          <div className="lg:col-span-3">
            <div className="card-lol min-h-[320px]">
              <div className="flex items-baseline justify-between mb-3">
                <h3 className="font-bold">
                  Statystyki roli: <span className="text-[#C89B3C]">{roleLabels[activeRole] || activeRole.toUpperCase()}</span>
                </h3>
                <div className="text-[11px] text-zinc-400">tylko % – bez liczby głosów</div>
              </div>

              {!statsQ.isLoading && activeStats.length === 0 && (
                <div className="text-zinc-400 text-sm py-10 text-center">
                  Brak danych dla tej roli.<br/>
                  <span className="text-[11px]">Daily może być jeszcze nieocenione – spróbuj za chwilę.</span>
                </div>
              )}

              {activeStats.length > 0 && (
                <div className="space-y-1.5 max-h-[440px] overflow-y-auto pr-1">
                  {activeStats.map((s, idx) => {
                    const pct = Number(s.pick_percent)
                    const isMyPick = myPickByRole[activeRole]?.player_slug === s.player_slug
                    return (
                      <div key={s.player_slug + idx} className={`flex items-center gap-3 px-2 py-[7px] rounded-xl ${isMyPick ? 'bg-amber-950/20 border border-amber-700/30' : 'hover:bg-zinc-900/60'}`}>
                        <div className="text-[11px] text-zinc-500 w-6 text-right tabular-nums">{idx+1}.</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className={`truncate text-[13px] ${isMyPick ? 'text-[#FDE08A] font-semibold' : 'text-zinc-200'}`}>
                              {isMyPick ? '▶ ' : ''}{s.player}
                            </span>
                            <span className="text-[12px] font-mono text-zinc-100" style={{minWidth: '52px', textAlign:'right'}}>
                              {pct.toFixed(pct < 1 ? 2 : 1)}%
                            </span>
                          </div>
                          {/* percent bar */}
                          <div className="h-[4px] bg-zinc-900 rounded mt-1 overflow-hidden">
                            <div
                              className="h-full rounded"
                              style={{
                                width: `${Math.min(100, Math.max(1.5, pct * 3))}%`,
                                background: s.rarity_tier === 'legendary' ? 'linear-gradient(90deg,#f59e0b,#fcd34d)' :
                                           s.rarity_tier === 'epic' ? '#a855f7' :
                                           s.rarity_tier === 'rare' ? '#3b82f6' : '#6b7280',
                                opacity: isMyPick ? 1 : 0.9
                              }}
                            />
                          </div>
                        </div>
                        <div className={`text-[10px] px-1.5 py-0.5 rounded-full border min-w-[62px] text-center ${
                          s.rarity_tier==='legendary' ? 'border-amber-500/40 text-amber-400 bg-amber-950/20' :
                          s.rarity_tier==='epic' ? 'border-fuchsia-500/30 text-fuchsia-300 bg-fuchsia-950/10' :
                          s.rarity_tier==='rare' ? 'border-blue-500/30 text-blue-300 bg-blue-950/10' :
                          'border-zinc-700 text-zinc-400'
                        }`}>
                          {s.rarity_tier}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              <div className="text-[10px] text-zinc-500 mt-3 border-t border-zinc-900 pt-2">
                Pokazujemy <b>tylko procenty</b> – bez liczby głosów, zgodnie z zasadami fair play.<br/>
                Rarity: Common &gt;20% • Rare 10–20% • Epic 1–10% • Legendary &lt;1% • 💎 Diamond – pierwszy pick na świecie
              </div>
            </div>
          </div>
        </div>

        {/* bottom nav */}
        <div className="flex flex-wrap gap-3 text-[12px]">
          <Link href={daily ? `/daily/${daily.id}` : '/'} className="pill hover:border-zinc-600">↺ Zagraj ponownie to Daily</Link>
          <Link href="/" className="pill hover:border-zinc-600">Dzisiejsze Daily →</Link>
          <Link href="/leaderboard" className="pill hover:border-zinc-600">Ranking Top 100</Link>
        </div>
      </div>
    </GameLayout>
  )
}
