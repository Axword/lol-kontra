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
    <div className="min-h-screen bg-bg text-ink flex">
      <Sidebar open={sidebarOpen} onClose={()=>setSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar
          errorsLeft={errorsLeft}
          onMenu={()=>setSidebarOpen(true)}
          onHelp={()=>setHelpOpen(true)}
          locale={locale}
          onLocaleChange={onLocaleChange}
        />
        {(leftTopSlot || rightTopSlot) && (
          <div className="px-3 sm:px-6 py-3 bg-panel border-b border-line flex items-center justify-between gap-3">
            <div className="min-w-0">{leftTopSlot}</div>
            <div className="min-w-0 text-right">{rightTopSlot}</div>
          </div>
        )}
        <main className="flex-1 px-3 sm:px-6 py-5 sm:py-7 max-w-[1180px] w-full mx-auto">
          {children}
        </main>
        <footer className="border-t border-line py-5 text-center text-[11px] text-muted">
          LoL Roster Challenge • inspirowane{' '}
          <a href="https://kontra.games" target="_blank" className="underline hover:text-ink transition-colors">kontra.games</a>{' '}
          • dane: Leaguepedia • Not affiliated with Riot Games
        </footer>
      </div>
      <HelpModal open={helpOpen} onClose={()=>setHelpOpen(false)} />
    </div>
  )
}
