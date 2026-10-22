'use client'
import { GuestProfile } from '@/lib/guest-profile'
import { formatPoints } from '@/lib/points'
import { usePrefs } from '@/lib/store'
import PlayerPortrait from '@/components/roster/PlayerPortrait'

export default function ProfileStatistics({ stats }: { stats: GuestProfile['stats'] }) {
  const locale = usePrefs((state) => state.locale)
  const pl = locale === 'pl'
  const count = (value: number | undefined) => (value ?? 0).toLocaleString(pl ? 'pl-PL' : 'en-GB')
  const percent = (value: number | undefined) => `${(value ?? 0).toLocaleString(pl ? 'pl-PL' : 'en-GB', { maximumFractionDigits: 1 })}%`
  const players = (stats.top_players?.length ? stats.top_players : stats.most_used_player ? [stats.most_used_player] : []).slice(0, 5)
  const metrics = [
    [pl ? 'Rozegrane gry' : 'Games played', count(stats.games_played)],
    [pl ? 'Suma punktów' : 'Total points', formatPoints(stats.total_points, locale)],
    [pl ? 'Najlepszy wynik' : 'Best score', formatPoints(stats.best_score, locale)],
    [pl ? 'Średni wynik' : 'Average score', formatPoints(stats.avg_points, locale)],
    [pl ? 'Poprawne odpowiedzi' : 'Correct answers', count(stats.correct_answers)],
    [pl ? 'Pomyłki' : 'Incorrect attempts', count(stats.incorrect_attempts)],
    [pl ? 'Skuteczność' : 'Accuracy', percent(stats.accuracy_percent)],
    [pl ? 'Gry bez pomyłki' : 'Perfect games', count(stats.perfect_games)],
    [pl ? 'Średnia popularność wyborów' : 'Average pick share', percent(stats.average_pick_percent)],
    [pl ? 'Diamentowe wybory' : 'Diamond picks', count(stats.diamond_picks)],
    [pl ? 'Wybory poniżej 2%' : 'Picks below 2%', count(stats.legendary_answers)],
    [pl ? 'Obecna seria dni' : 'Current daily streak', count(stats.current_streak)],
    [pl ? 'Najdłuższa seria dni' : 'Longest daily streak', count(stats.max_streak)],
  ]
  return <div className="space-y-6 border-t pt-5" style={{ borderColor: 'var(--line)' }}>
    <dl className="grid grid-cols-2 gap-x-8 gap-y-5">
      {metrics.map(([label, value]) => <div key={label}>
        <dt className="text-xs" style={{ color: 'var(--text-faint)' }}>{label}</dt>
        <dd className="mt-1 text-xl font-semibold tabular">{value}</dd>
      </div>)}
    </dl>
    <section className="border-t pt-5" style={{ borderColor: 'var(--line)' }}>
      <h2 className="text-sm font-semibold">{pl ? 'Najczęściej wybierani zawodnicy' : 'Most picked players'}</h2>
      {players.length === 0
        ? <p className="mt-3 text-sm" style={{ color: 'var(--text-faint)' }}>{pl ? 'Brak poprawnych wyborów.' : 'No correct picks yet.'}</p>
        : <ol className="mt-4 space-y-3">
          {players.map((player) => <li key={player.id} className="flex items-center gap-3">
            <PlayerPortrait url={player.portrait_url} fallback={<span aria-hidden="true" className="h-12 w-12 shrink-0 border bg-[var(--panel-2)]" style={{ borderColor: 'var(--line)' }} />} />
            <span className="min-w-0 flex-1 truncate text-sm font-semibold">{player.nickname}</span>
            <span className="shrink-0 text-xs tabular" style={{ color: 'var(--text-faint)' }}>{pl ? 'Wybory' : 'Picks'}: {count(player.pick_count)}</span>
          </li>)}
        </ol>}
    </section>
  </div>
}
