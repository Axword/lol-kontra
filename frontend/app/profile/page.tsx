'use client'
import { useGameStore } from '@/lib/store'
import Link from 'next/link'

export default function ProfilePage() {
  const games = useGameStore(s => s.games)
  const finished = Object.values(games).filter(g => g.finished && g.score != null)
  const scores = finished.map(g => g.score as number)
  const avg = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10 : null
  const best = scores.length ? Math.min(...scores) : null
  const diamonds = Object.values(games).reduce((s, g) => s + Object.values(g.picks).filter(p => p.is_diamond_pick).length, 0)
  const legendary = Object.values(games).reduce((s, g) => s + Object.values(g.picks).filter(p => p.is_correct && p.rarity_tier === 'legendary').length, 0)

  return (
    <div className="min-h-screen bg-[#06080c] text-[#E8E6E3] px-4 py-8 max-w-3xl mx-auto space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">Profil</h1>
        <Link href="/" className="text-[#C89B3C] hover:underline text-sm">← wróć do gry</Link>
      </div>
      <div className="card-lol">
        <p className="text-lol-muted text-sm">
          Twoje wyniki i postępy zapisywane są lokalnie w przeglądarce – bez konta i bez backendu.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          ['Rozegrane', String(finished.length)],
          ['Średni wynik', avg != null ? String(avg) : '—'],
          ['Najlepszy wynik', best != null ? String(best) : '—'],
          ['Diamond Picks 💎', String(diamonds)],
          ['Legendary ⭐', String(legendary)],
        ].map(([k, v]) => (
          <div key={k} className="card-lol">
            <div className="text-xs text-lol-muted">{k}</div>
            <div className="text-2xl font-bold text-lol-gold">{v}</div>
          </div>
        ))}
      </div>
      <div className="text-[11px] text-zinc-500">niższy wynik = lepszy • start 500 pkt</div>
    </div>
  )
}
