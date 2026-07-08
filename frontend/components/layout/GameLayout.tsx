'use client'
import { useState, ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import HelpModal from '../ui/HelpModal'

export default function GameLayout({
  children,
  leftTopSlot,
  rightTopSlot,
  errorsLeft = 10,
  locale = 'pl',
  onLocaleChange
}: {
  children: ReactNode,
  leftTopSlot?: ReactNode,
  rightTopSlot?: ReactNode,
  errorsLeft?: number,
  locale?: string,
  onLocaleChange?: (l:string)=>void
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#06080c] text-[#E8E6E3] flex">
      <Sidebar open={sidebarOpen} onClose={()=>setSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        {/* TopBar – 2 rows combined in component */}
        <TopBar
          errorsLeft={errorsLeft}
          onMenu={()=>setSidebarOpen(true)}
          onHelp={()=>setHelpOpen(true)}
          locale={locale}
          onLocaleChange={onLocaleChange}
        />
        {/* optional injected left/right top slots – e.g. score */}
        {(leftTopSlot || rightTopSlot) && (
          <div className="px-3 sm:px-6 py-3 bg-[#0a0e13] border-b border-zinc-900 flex items-center justify-between gap-3">
            <div className="min-w-0">{leftTopSlot}</div>
            <div className="min-w-0 text-right">{rightTopSlot}</div>
          </div>
        )}
        <main className="flex-1 px-3 sm:px-6 py-5 sm:py-7 max-w-[1200px] w-full mx-auto">
          {children}
        </main>
        <footer className="border-t border-zinc-900 py-5 text-center text-[11px] text-zinc-500">
          LoL Roster Challenge • inspirowane <a href="https://kontra.games" target="_blank" className="underline hover:text-zinc-300">kontra.games</a> • dane: Leaguepedia • Not affiliated with Riot Games
        </footer>
      </div>
      <HelpModal open={helpOpen} onClose={()=>setHelpOpen(false)} />
    </div>
  )
}
