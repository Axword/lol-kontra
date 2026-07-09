'use client'
import { useState, ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import HelpModal from '../ui/HelpModal'

export default function GameLayout({
  children,
  errorsLeft = 10,
  locale = 'pl',
  onLocaleChange,
}: {
  children: ReactNode
  errorsLeft?: number
  locale?: string
  onLocaleChange?: (l: string) => void
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#06080c] text-[#E8E6E3] flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar
          errorsLeft={errorsLeft}
          onMenu={() => setSidebarOpen(true)}
          onHelp={() => setHelpOpen(true)}
          locale={locale}
          onLocaleChange={onLocaleChange}
        />
        <main className="flex-1 px-3 sm:px-6 py-5 sm:py-7 max-w-[1100px] w-full mx-auto">
          {children}
        </main>
        <footer className="border-t border-zinc-900 py-4 text-center text-[11px] text-zinc-600">
          LoL Roster Challenge · dane: Leaguepedia · not affiliated with Riot Games
        </footer>
      </div>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
