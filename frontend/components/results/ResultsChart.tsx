'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useMemo, useState } from 'react'

type ScorePoint = { score: number, count: number }

export default function ResultsChart({
  dailyId,
  userScore,
  totalPlayers,
}: {
  dailyId?: number,
  userScore: number,
  totalPlayers?: number
}) {
  const [binSize, setBinSize] = useState(5) // 1, 2, 5, 10 punktowe kubełki – user może przełączać

  const { data, isLoading } = useQuery({
    queryKey: ['score-dist', dailyId, userScore],
    queryFn: async () => {
      if (!dailyId) return null
      const r = await api.get(`/dailies/${dailyId}/score-distribution/`, { params: { user_score: userScore }})
      return r.data
    },
    enabled: !!dailyId,
    staleTime: 15000,
    refetchInterval: 30000,
  })

  const distribution: ScorePoint[] = data?.distribution || []
  const stats = {
    total: data?.total_submissions ?? totalPlayers ?? 0,
    avg: data?.avg_score ?? null,
    max: data?.max_score ?? null,
    min: data?.min_score ?? 0,
    percentile: data?.percentile ?? null,
    rank: data?.rank ?? null,
    stddev: data?.stddev ?? null,
  }

  // build binned histogram
  const binned = useMemo(() => {
    if (!distribution.length) return []
    const minScore = Math.min(...distribution.map(d=>d.score), 0)
    const maxScore = Math.max(...distribution.map(d=>d.score), userScore, 10)
    const start = Math.floor(minScore / binSize) * binSize
    const end = Math.ceil(maxScore / binSize) * binSize
    const buckets: {x0:number, x1:number, count:number, hasUser:boolean}[] = []
    for (let x = start; x <= end; x += binSize) {
      const count = distribution
        .filter(d => d.score >= x && d.score < x + binSize)
        .reduce((s, d) => s + d.count, 0)
      const hasUser = userScore >= x && userScore < x + binSize
      buckets.push({ x0: x, x1: x + binSize -1, count, hasUser })
    }
    return buckets
  }, [distribution, binSize, userScore])

  const maxCount = Math.max(1, ...binned.map(b=>b.count))

  // fallback mock if no API data yet
  const useMock = binned.length === 0
  const mockBuckets = [
    {x0:0,x1:29,count:18,hasUser: userScore>=0&&userScore<30},
    {x0:30,x1:59,count:34,hasUser: userScore>=30&&userScore<60},
    {x0:60,x1:99,count:52,hasUser: userScore>=60&&userScore<100},
    {x0:100,x1:149,count:29,hasUser: userScore>=100&&userScore<150},
    {x0:150,x1:249,count:14,hasUser: userScore>=150&&userScore<250},
    {x0:250,x1:600,count:5,hasUser: userScore>=250},
  ]
  const displayBuckets = useMock ? mockBuckets : binned
  const displayMax = useMock ? 52 : maxCount

  return (
    <div className="card-lol">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 className="font-bold">Rozkład punktów – Daily #{dailyId || '?'}</h3>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-zinc-400">dokładność:</span>
          {[1,2,5,10,20].map(b=>(
            <button
              key={b}
              onClick={()=>setBinSize(b)}
              className={`px-2 py-0.5 rounded border text-[11px] transition ${binSize===b 
                ? 'border-[#C89B3C] text-[#C89B3C] bg-[#C89B3C]/10' 
                : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`}
            >{b}pkt</button>
          ))}
        </div>
      </div>

      {/* high-res histogram – scrollable if many bins */}
      <div className="relative w-full overflow-x-auto">
        <div className="min-w-[640px]">
          <div className="flex items-end gap-[2px] h-[176px] px-1 border-b border-zinc-800">
            {displayBuckets.map((b, i) => {
              const h = Math.max(3, Math.round((b.count / displayMax) * 150))
              return (
                <div key={i} className="flex-1 flex flex-col items-center justify-end group relative" style={{minWidth: binSize===1 ? 6 : binSize<=5 ? 10 : 18}}>
                  {/* count label on hover / top when user */}
                  <div className={`text-[9px] mb-0.5 transition-opacity ${b.hasUser ? 'text-[#C89B3C] opacity-100 font-bold' : 'text-zinc-500 opacity-0 group-hover:opacity-100'}`}>
                    {b.count > 0 ? b.count : ''}
                  </div>
                  <div
                    className={`w-full rounded-t-sm transition-all ${b.hasUser ? '' : 'hover:brightness-125'}`}
                    style={{
                      height: h,
                      background: b.hasUser
                        ? 'linear-gradient(180deg,#FDE08A 0%, #C89B3C 45%, #9a7328 100%)'
                        : b.count === 0
                          ? '#1a1d23'
                          : 'linear-gradient(180deg,#3a3f4a 0%, #2a2f3a 100%)',
                      boxShadow: b.hasUser ? '0 0 14px rgba(200,155,60,0.45), inset 0 0 8px rgba(255,255,255,0.15)' : undefined,
                      outline: b.hasUser ? '1px solid #fff4' : undefined
                    }}
                    title={`${b.x0}–${b.x1} pkt: ${b.count} graczy${b.hasUser ? ' ← TY' : ''}`}
                  />
                </div>
              )
            })}
          </div>
          {/* x axis labels – show every Nth to avoid clutter */}
          <div className="flex gap-[2px] px-1 mt-1 text-[9px] text-zinc-500 overflow-hidden" style={{minWidth: '640px'}}>
            {displayBuckets.map((b,i)=>{
              const show = displayBuckets.length < 40 || i % Math.ceil(displayBuckets.length/20) === 0
              return (
                <div key={i} className="flex-1 text-center truncate" style={{minWidth: binSize===1 ? 6 : binSize<=5 ? 10 : 18}}>
                  {show ? b.x0 : ''}
                </div>
              )
            })}
          </div>
          <div className="text-[10px] text-zinc-500 text-center mt-0.5">punkty →</div>
        </div>
      </div>

      {/* stats row */}
      <div className="mt-4 pt-3 border-t border-zinc-800 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-[12px]">
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Twój wynik</div>
          <div className="text-[18px] font-extrabold text-[#C89B3C]">{userScore} <span className="text-xs font-normal text-zinc-400">pkt</span></div>
        </div>
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Pozycja</div>
          <div className="text-[16px] font-bold text-white">
            {stats.rank ? `#${stats.rank}` : '—'}
            <span className="text-zinc-400 text-[11px] font-normal"> / {stats.total || totalPlayers || '?'}</span>
          </div>
        </div>
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Percentyl</div>
          <div className="text-[16px] font-bold text-emerald-400">
            {stats.percentile !== null ? `${stats.percentile}%` : '—'}
          </div>
          <div className="text-[10px] text-zinc-500">lepszy niż</div>
        </div>
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Średnia</div>
          <div className="text-[15px] font-semibold text-white">{stats.avg ?? '—'}</div>
        </div>
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Max</div>
          <div className="text-[15px] font-semibold text-[#F59E0B]">{stats.max ?? '—'}</div>
        </div>
        <div>
          <div className="text-zinc-400 text-[10px] uppercase">Graczy</div>
          <div className="text-[15px] font-semibold">{stats.total || totalPlayers || '—'}</div>
        </div>
      </div>

      {/* legend */}
      <div className="mt-3 text-[10px] text-zinc-500 flex flex-wrap gap-3">
        <span>kubełek: <b className="text-zinc-300">{binSize} pkt</b> – kliknij 1/2/5/10/20 by zmienić dokładność</span>
        <span>• złoty słupek = Twój przedział</span>
        <span>• najedź myszką by zobaczyć dokładną liczbę graczy</span>
        {stats.stddev && <span>• σ = {stats.stddev}</span>}
        {!data && <span className="text-amber-400">• dane demo – API /score-distribution odpowie live po pierwszym submit</span>}
      </div>
    </div>
  )
}
