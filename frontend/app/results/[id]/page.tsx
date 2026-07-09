'use client'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import GameLayout from '@/components/layout/GameLayout'
import { useState, useMemo } from 'react'
import Link from 'next/link'

type AnswerStat = {
  slot_id: number
  slot_role: string
  player: string
  player_slug: string
  pick_percent: number
  rarity_tier: string
  pick_count?: number
}

export default function ResultsPage() {
  const params = useParams()
  const id = params?.id as string
  const [selectedRole, setSelectedRole] = useState<string | null>(null)

  const dailyQ = useQuery({
    queryKey: ['daily', id],
    queryFn: async () => (await api.get(`/dailies/${id}/`)).data,
    enabled: !!id,
  })
  const mySubQ = useQuery({
    queryKey: ['my-submission-result', id],
    queryFn: async () => {
      try {
        const guest = typeof window !== 'undefined' ? localStorage.getItem('guest_token') || '' : ''
        const r = await api.get('/submissions/me/', { params: { daily_id: id, guest_token: guest } })
        return r.data
      } catch { return null }
    },
    enabled: !!id,
    refetchInterval: 8000,
  })
  const statsQ = useQuery({
    queryKey: ['answer-stats', id],
    queryFn: async () => (await api.get(`/dailies/${id}/answer-stats/`)).data,
    enabled: !!id,
    refetchInterval: 15000,
  })

  const daily = dailyQ.data
  const mySub = mySubQ.data
  const stats: AnswerStat[] = statsQ.data?.results || []

  const statsByRole = useMemo(() => {
    const map: Record<string, AnswerStat[]> = {}
    stats.forEach(s => {
      if (!map[s.slot_role]) map[s.slot_role] = []
      map[s.slot_role].push(s)
    })
    Object.keys(map).forEach(k => { map[k].sort((a, b) => b.pick_percent - a.pick_percent) })
    return map
  }, [stats])

  const roles: Array<'top' | 'jungle' | 'mid' | 'adc' | 'support'> = ['top', 'jungle', 'mid', 'adc', 'support']
  const roleLabels: Record<string, string> = { top: 'TOP', jungle: 'JNG', mid: 'MID', adc: 'ADC', support: 'SUP' }
  const activeRole = selectedRole || daily?.slots?.[0]?.role || 'mid'
  const activeStats = statsByRole[activeRole] || []

  const myPickByRole: Record<string, any> = {}
  if (mySub?.answers) {
    mySub.answers.forEach((a: any) => { myPickByRole[a.slot_role] = a })
  }

  const totalPoints = mySub?.total_points ?? null

  return (
    <GameLayout>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] text-zinc-500 uppercase tracking-wider">Wyniki Daily #{id}</div>
            <div className="text-[20px] font-bold text-white">
              {totalPoints !== null ? <span className="text-[#C89B3C]">{totalPoints} pkt</span> : '—'}
              {daily && <span className="text-zinc-500 text-[14px] font-normal ml-2">{daily.date}</span>}
            </div>
          </div>
          <Link href={daily ? `/daily/${daily.id}` : '/'} className="text-[12px] text-zinc-400 hover:text-white transition">
            ← wróć
          </Link>
        </div>

        <div className="grid lg:grid-cols-5 gap-4">
          {/* left – your roster */}
          <div className="lg:col-span-2 space-y-1.5">
            {roles.map(role => {
              const pick = myPickByRole[role]
              const isActive = activeRole === role
              return (
                <button
                  key={role}
                  onClick={() => setSelectedRole(role)}
                  className={`w-full text-left rounded-xl border px-3 py-2.5 transition flex items-center gap-3
                    ${isActive
                      ? 'border-[#C89B3C]/60 bg-[#111822]'
                      : 'border-zinc-800 bg-[#0d1117] hover:border-zinc-700'
                    }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/roles/${role}.svg`}
                    alt={role}
                    className="w-8 h-8 opacity-80"
                    style={{ filter: pick ? 'brightness(1.1)' : 'grayscale(1) brightness(.6)' }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[9px] text-[#C8AC6E] uppercase tracking-wide">{roleLabels[role]}</div>
                    <div className="font-semibold truncate text-[13px]">
                      {pick ? pick.player_nickname : <span className="text-zinc-600">—</span>}
                    </div>
                    {pick && (
                      <div className="text-[10px] mt-px">
                        {pick.is_correct ? (
                          <span className={
                            pick.rarity_tier === 'legendary' ? 'text-amber-400' :
                            pick.rarity_tier === 'epic' ? 'text-fuchsia-400' :
                            pick.rarity_tier === 'rare' ? 'text-blue-400' : 'text-zinc-400'
                          }>
                            {pick.rarity_tier} · {pick.points_awarded} pkt{pick.is_diamond_pick ? ' 💎' : ''}
                          </span>
                        ) : (
                          <span className="text-red-500">błąd</span>
                        )}
                      </div>
                    )}
                  </div>
                  <span className="text-zinc-700 text-[12px]">›</span>
                </button>
              )
            })}
          </div>

          {/* right – stats */}
          <div className="lg:col-span-3">
            <div className="card-lol min-h-[280px]">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[13px] font-semibold text-zinc-200 uppercase tracking-wide">
                  {roleLabels[activeRole]}
                </h3>
                <span className="text-[10px] text-zinc-600">tylko %</span>
              </div>

              {!statsQ.isLoading && activeStats.length === 0 && (
                <div className="text-zinc-500 text-sm py-10 text-center">Brak danych</div>
              )}

              <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
                {activeStats.map((s, idx) => {
                  const pct = Number(s.pick_percent)
                  const isMyPick = myPickByRole[activeRole]?.player_slug === s.player_slug
                  return (
                    <div
                      key={s.player_slug + idx}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-lg ${isMyPick ? 'bg-amber-950/20' : ''}`}
                    >
                      <div className="text-[10px] text-zinc-600 w-5 text-right tabular-nums">{idx + 1}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className={`truncate text-[12px] ${isMyPick ? 'text-[#FDE08A] font-semibold' : 'text-zinc-200'}`}>
                            {isMyPick ? '▶ ' : ''}{s.player}
                          </span>
                          <span className="text-[11px] font-mono text-zinc-300 tabular-nums">{pct.toFixed(pct < 1 ? 2 : 1)}%</span>
                        </div>
                        <div className="h-[3px] bg-zinc-900 rounded mt-1 overflow-hidden">
                          <div
                            className="h-full rounded"
                            style={{
                              width: `${Math.min(100, Math.max(1.5, pct * 3))}%`,
                              background:
                                s.rarity_tier === 'legendary' ? '#f59e0b' :
                                s.rarity_tier === 'epic' ? '#a855f7' :
                                s.rarity_tier === 'rare' ? '#3b82f6' : '#52525b',
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-[12px]">
          <Link href={daily ? `/daily/${daily.id}` : '/'} className="pill">↺ Zagraj ponownie</Link>
          <Link href="/" className="pill">Dzisiejsze Daily →</Link>
        </div>
      </div>
    </GameLayout>
  )
}
