'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Entry = {
  username: string,
  total_points: number,
  diamond_picks: number,
  legendary_answers: number,
  games_played?: number,
  best_score?: number
}

export default function DailyTop10({ dailyId }: { dailyId?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['leaderboard', dailyId || 'all'],
    queryFn: async () => (await api.get('/leaderboard/', { params: dailyId ? { daily_id: dailyId } : {} })).data,
    staleTime: 30_000
  })

  const rows: Entry[] = data?.results?.slice(0,10) || []

  return (
    <div className="card-lol">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="font-bold">Top 10 – {dailyId ? `Daily #${dailyId}` : 'All-Time'}</h3>
        <a href="/leaderboard" className="text-[11px] text-[#C89B3C] hover:underline">pełny ranking →</a>
      </div>

      {isLoading && <div className="text-sm text-zinc-400 py-6 text-center">Ładowanie…</div>}

      {!isLoading && rows.length === 0 && (
        <div className="text-sm text-zinc-500 py-6 text-center">Brak danych rankingowych – bądź pierwszy!</div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="text-[11px] text-zinc-400 border-b border-zinc-800">
              <tr className="[&>th]:py-2 [&>th]:font-medium [&>th]:text-left">
                <th className="w-8">#</th>
                <th>Gracz</th>
                <th className="text-right">Pkt</th>
                <th className="text-center">💎</th>
                <th className="text-center">⭐</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-zinc-900 last:border-0 hover:bg-zinc-900/40">
                  <td className="py-[10px] text-zinc-400">{i+1}</td>
                  <td className="py-[10px] font-medium">
                    <span className={i<3 ? 'text-[#C89B3C]' : 'text-white'}>{r.username}</span>
                  </td>
                  <td className="py-[10px] text-right font-semibold">{r.total_points}</td>
                  <td className="py-[10px] text-center text-[#22D3EE]">{r.diamond_picks || 0}</td>
                  <td className="py-[10px] text-center text-[#F59E0B]">{r.legendary_answers || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="text-[10px] text-zinc-500 mt-2">💎 = Diamond Picks • ⭐ = Legendary answers</div>
    </div>
  )
}
