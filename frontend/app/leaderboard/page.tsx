'use client'
import { useGameStore } from '@/lib/store'
import Link from 'next/link'

export default function LeaderboardPage() {
  const games = useGameStore(s => s.games)
  const rows = Object.entries(games)
    .filter(([, g]) => g.finished && g.score != null)
    .map(([id, g]) => ({
      id: Number(id),
      date: g.date || '—',
      score: g.score as number,
      correct: Object.values(g.picks).filter(p => p.is_correct).length,
      diamonds: Object.values(g.picks).filter(p => p.is_diamond_pick).length,
      legendary: Object.values(g.picks).filter(p => p.is_correct && p.rarity_tier === 'legendary').length,
      errors: g.errors,
    }))
    .sort((a, b) => a.score - b.score)

  return (
    <div className="min-h-screen bg-bg text-ink px-4 py-8 max-w-3xl mx-auto space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">Moje wyniki</h1>
        <Link href="/" className="text-accent hover:underline text-sm">← wróć do gry</Link>
      </div>
      <div className="panel">
        {rows.length === 0 ? (
          <div className="py-8 text-center text-muted">
            Brak zakończonych gier – zagraj pierwsze Daily!<br />
            <Link href="/" className="text-accent hover:underline text-sm mt-2 inline-block">Zagraj teraz →</Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-muted text-[11px] border-b border-line">
              <tr className="[&>th]:py-2 [&>th]:text-left">
                <th>#</th><th>Daily</th><th>Data</th>
                <th className="text-right">Wynik</th>
                <th className="text-center">✓</th>
                <th className="text-center">✗</th>
                <th className="text-center">◆</th>
                <th className="text-center">★</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} className="border-t border-line hover:bg-surface/60">
                  <td className="py-2 text-muted">{i + 1}</td>
                  <td className="font-medium">
                    <Link href={`/daily/${r.id}`} className="hover:text-accent transition-colors">{r.id}</Link>
                  </td>
                  <td className="text-muted">{r.date}</td>
                  <td className="text-right font-semibold text-accent mono">{r.score}</td>
                  <td className="text-center text-warn">{r.correct}</td>
                  <td className="text-center text-red">{r.errors}</td>
                  <td className="text-center text-ink">{r.diamonds || ''}</td>
                  <td className="text-center text-warn">{r.legendary || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="text-[11px] text-muted">
        Niższy wynik = lepszy (start 500, każde trafienie odejmuje punkty) • ◆ Diamond Picks • ★ Legendary • wyniki zapisywane lokalnie w Twojej przeglądarce
      </div>
    </div>
  )
}
