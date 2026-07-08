'use client'
export default function ProfilePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Profil</h1>
      <div className="card-lol">
        <p className="text-lol-muted">Zaloguj się przez Google / Discord aby zapisywać historię gier, streaki i Diamond Picks.</p>
        <div className="mt-4 flex gap-3">
          <button className="pill">Zaloguj Google (wkrótce)</button>
          <button className="pill">Zaloguj Discord (wkrótce)</button>
        </div>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        {[
          ['Rozegrane', '0'],
          ['Średni wynik', '—'],
          ['Diamond Picks', '0'],
          ['Legendary', '0'],
          ['Best score', '—'],
          ['Streak', '0'],
        ].map(([k,v])=>(
          <div key={k} className="card-lol">
            <div className="text-xs text-lol-muted">{k}</div>
            <div className="text-2xl font-bold text-lol-gold">{v}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
