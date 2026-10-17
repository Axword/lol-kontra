'use client'
import { useState, ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import HelpModal from '../ui/HelpModal'

type Props = {
  children: ReactNode
  dailyId?: number
  dailyDate?: string
  score?: number | null
  correct?: number
  slotsTotal?: number
  errorsLeft?: number
  errorsTotal?: number
}

export default function GameLayout({
  children, dailyId, dailyDate, score, correct, slotsTotal, errorsLeft, errorsTotal,
}: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  return (
    <div className="min-h-screen bg-bg text-ink flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar
          dailyId={dailyId}
          dailyDate={dailyDate}
          score={score}
          correct={correct}
          slotsTotal={slotsTotal}
          errorsLeft={errorsLeft}
          errorsTotal={errorsTotal}
          onMenu={() => setSidebarOpen(true)}
          onHelp={() => setHelpOpen(true)}
        />
        <main className="flex-1 px-3 sm:px-5 py-4 sm:py-6 max-w-[1180px] w-full mx-auto">
          {children}
        </main>
        <footer className="border-t border-line py-5 text-center text-[11px] text-muted">
          Dane: Leaguepedia · projekt fanowski, niezwiązany z Riot Games
        </footer>
      </div>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
