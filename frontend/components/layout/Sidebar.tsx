'use client'
import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const games = [
  { id: 'worldsxi', label: 'Worlds XI', labelPl: 'Worlds XI', active: true, icon: '🏆' },
  { id: 'lck', label: 'LCK Challenge', labelPl: 'LCK Challenge', active: false, soon: true },
  { id: 'lec', label: 'LEC Challenge', labelPl: 'LEC Challenge', active: false, soon: true },
  { id: 'allstar', label: 'All-Star Draft', labelPl: 'All-Star Draft', active: false, soon: true },
]

export default function Sidebar({ open, onClose }: { open: boolean, onClose: () => void }) {
  const pathname = usePathname()
  return (
    <>
      {/* backdrop mobile */}
      <div
        className={`fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />
      <aside className={`fixed lg:sticky top-0 left-0 h-screen z-50 w-[280px] bg-[#0b0f16] border-r border-zinc-800 flex flex-col transition-transform duration-250
        ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        {/* logo */}
        <div className="h-[64px] px-5 flex items-center border-b border-zinc-800">
          <div className="font-extrabold tracking-tight text-[18px]">
            <span className="text-[#C89B3C]">Worlds</span><span className="text-white"> XI</span>
          </div>
          <button onClick={onClose} className="lg:hidden ml-auto text-zinc-400">✕</button>
        </div>

        {/* game picker */}
        <div className="p-4">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2 px-1">Wybierz grę</div>
          <nav className="space-y-1.5">
            {games.map(g => (
              <Link
                key={g.id}
                href={g.active ? '/' : '#'}
                onClick={e => { if(!g.active) e.preventDefault() }}
                className={`flex items-center gap-3 px-3 py-[10px] rounded-xl border transition
                  ${g.active 
                    ? 'bg-[#121a23] border-[#C89B3C]/40 text-white' 
                    : 'border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                  }`}
              >
                <span className="text-lg w-6 text-center">{g.icon || '🎮'}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold truncate">{g.labelPl}</div>
                  <div className="text-[10px] text-zinc-500">{g.label}</div>
                </div>
                {g.soon && <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">soon</span>}
                {g.active && <span className="w-1.5 h-1.5 rounded-full bg-[#C89B3C]" />}
              </Link>
            ))}
          </nav>
        </div>

        <div className="mt-auto border-t border-zinc-800 p-4 text-[11px] text-zinc-500 space-y-2">
          <div>Daily Challenge<br/>LoL Esports</div>
          <div className="text-[10px] text-zinc-600">
            Inspirowane <a href="https://kontra.games" target="_blank" className="underline hover:text-zinc-400">kontra.games</a><br/>
            Dane: Leaguepedia<br/>
            Not affiliated with Riot
          </div>
          <div className="flex gap-3 pt-1 text-zinc-400">
            <a href="/leaderboard" className="hover:text-white">Ranking</a>
            <a href="#" className="hover:text-white">Regulamin</a>
            <a href="#" className="hover:text-white">Kontakt</a>
          </div>
        </div>
      </aside>
    </>
  )
}
