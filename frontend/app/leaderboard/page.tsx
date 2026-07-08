'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export default function LeaderboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: async () => (await api.get('/leaderboard/')).data
  })

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Ranking</h1>
      <div className="card-lol">
        {isLoading ? 'Ładowanie…' : (
          <table className="w-full text-sm">
            <thead className="text-lol-muted">
              <tr><th className="text-left">#</th><th className="text-left">Gracz</th><th>Punkty</th><th>Gry</th><th>💎</th><th>Legendary</th></tr>
            </thead>
            <tbody>
              {data?.results?.map((u:any, i:number)=>(
                <tr key={i} className="border-t border-zinc-900">
                  <td className="py-2">{i+1}</td>
                  <td className="font-medium">{u.username}</td>
                  <td>{u.total_points}</td>
                  <td>{u.games_played}</td>
                  <td>{u.diamond_picks}</td>
                  <td>{u.legendary_answers}</td>
                </tr>
              )) || <tr><td colSpan={6} className="py-6 text-center text-lol-muted">Brak danych – zagraj pierwsze Daily!</td></tr>}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
