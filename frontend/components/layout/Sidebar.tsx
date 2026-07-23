'use client'
import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const games = [
  { id: 'worldsxi', label: 'Worlds XI', labelPl: 'Worlds XI', active: true, monogram: 'W' },
  { id: 'lck', label: 'LCK Challenge', labelPl: 'LCK Challenge', active: false, soon: true, monogram: 'L' },
  { id: 'lec', label: 'LEC Challenge', labelPl: 'LEC Challenge', active: false, soon: true, monogram: 'E' },
  { id: 'allstar', label: 'All-Star Draft', labelPl: 'All-Star Draft', active: false, soon: true, monogram: 'A' },
]

export default function Sidebar({ open, onClose }: { open: boolean, onClose: () => void }) {
  const pathname = usePathname()
  return (
    <>
      <div
        className={`fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />
      <aside className={`fixed lg:sticky top-0 left-0 h-screen z-50 w-[280px] bg-panel border-r border-line flex flex-col transition-transform duration-150
        ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="h-[64px] px-5 flex items-center border-b border-line">
          <div className="font-extrabold tracking-tight text-[18px]">
            <span className="text-ink">Worlds</span><span className="text-accent"> XI</span>
          </div>
          <button onClick={onClose} className="lg:hidden ml-auto text-muted hover:text-ink transition-colors">✕</button>
        </div>

        <div className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted mb-2 px-1">Wybierz grę</div>
          <nav className="space-y-1.5">
            {games.map(g => (
              <Link
                key={g.id}
                href={g.active ? '/' : '#'}
                onClick={e => { if(!g.active) e.preventDefault() }}
                className={`flex items-center gap-3 px-3 py-[10px] rounded-control border transition-colors
                  ${g.active
                    ? 'tonal'
                    : 'border-line text-muted hover:border-muted hover:text-ink'
                  }`}
              >
                <span className={`w-7 h-7 rounded-control border flex items-center justify-center text-[12px] font-semibold
                  ${g.active ? 'border-accent text-accent bg-accent-soft' : 'border-line text-muted'}`}>
                  {g.monogram}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold truncate text-ink">{g.labelPl}</div>
                  <div className="text-[10px] text-muted">{g.label}</div>
                </div>
                {g.soon && <span className="text-[9px] px-1.5 py-0.5 rounded bg-surface border border-line text-muted">soon</span>}
                {g.active && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
              </Link>
            ))}
          </nav>
        </div>

        <div className="mt-auto border-t border-line p-4 text-[11px] text-muted space-y-2">
          <div>Daily Challenge<br/>LoL Esports</div>
          <div className="text-[10px] text-muted/80">
            Inspirowane <a href="https://kontra.games" target="_blank" className="underline hover:text-ink transition-colors">kontra.games</a><br/>
            Dane: Leaguepedia<br/>
            Not affiliated with Riot
          </div>
          <div className="flex gap-3 pt-1 text-muted">
            <a href="/leaderboard" className="hover:text-ink transition-colors">Ranking</a>
            <a href="#" className="hover:text-ink transition-colors">Regulamin</a>
            <a href="#" className="hover:text-ink transition-colors">Kontakt</a>
          </div>
        </div>
      </aside>
    </>
  )
}
