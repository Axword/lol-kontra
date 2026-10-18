'use client'
import { ReactNode, useCallback, useState } from 'react'
import HelpModal from '../ui/HelpModal'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { usePrefs } from '@/lib/store'
import { formatPoints } from '@/lib/points'

type Props = {
  children: ReactNode
  dailyId?: number
  dailyDate?: string
  score?: number | null
  correctCount?: number
  slotsTotal?: number
  errorsLeft?: number | null
  maxErrors?: number | null
}

export default function GameLayout({
  children, dailyId, dailyDate, score, correctCount, slotsTotal, errorsLeft, maxErrors,
}: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const locale = usePrefs((s) => s.locale)
  const closeSidebar = useCallback(() => setSidebarOpen(false), [])
  const showGameHeader = dailyId != null && (score !== undefined || correctCount !== undefined || errorsLeft !== undefined)
  const dateLabel = dailyDate
    ? new Date(dailyDate + 'T00:00:00').toLocaleDateString(
        locale === 'pl' ? 'pl-PL' : 'en-GB',
        { day: 'numeric', month: 'long', year: 'numeric' }
      )
    : null

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--bg)' }}>
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar
          onMenu={() => setSidebarOpen(true)}
          onHelp={() => { setSidebarOpen(false); setHelpOpen(true) }}
        />
        <main className="flex-1 w-full max-w-[1180px] mx-auto px-3 sm:px-6 py-6 sm:py-8">
          {showGameHeader && (
            <div className="max-w-[1000px] mx-auto mb-4">
              <div className="flex flex-wrap items-end justify-between gap-2 mb-4">
                <h1 className="text-[28px] sm:text-[34px] leading-none font-bold tracking-[-.045em]" style={{ color: 'var(--text)' }}>WORDS V</h1>
                <div className="text-[12px] flex items-center gap-3" style={{ color: 'var(--text-faint)' }}>
                  {dateLabel && <span>{dateLabel}</span>}
                  <span className="tabular">#{dailyId}</span>
                </div>
              </div>
              <dl
                className="grid grid-cols-3 sm:flex sm:items-center sm:justify-between gap-3 border px-3 sm:px-4 py-3"
                style={{ background: '#fff', borderColor: 'var(--line)' }}
              >
                <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
                  <dt className="text-[11px] sm:text-[12px]" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? 'Wynik' : 'Score'}</dt>
                  <dd className="tabular text-[20px] font-semibold leading-none" style={{ color: 'var(--gold)' }}>{score == null ? '—' : formatPoints(score, locale)}</dd>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
                  <dt className="text-[11px] sm:text-[12px]" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? 'Uzupełnione' : 'Completed'}</dt>
                  <dd className="tabular text-[20px] font-semibold leading-none">
                    {correctCount ?? '—'}<span className="text-[15px] font-normal" style={{ color: 'var(--text-faint)' }}> / {slotsTotal ?? '—'}</span>
                  </dd>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
                  <dt className="text-[11px] sm:text-[12px]" style={{ color: 'var(--text-faint)' }}>{locale === 'pl' ? 'Życia' : 'Lives'}</dt>
                  <dd className="tabular text-[20px] font-semibold leading-none" style={{ color: errorsLeft === 0 ? 'var(--bad)' : 'var(--text)' }}>
                    {errorsLeft ?? '—'}<span className="text-[15px] font-normal" style={{ color: 'var(--text-faint)' }}> / {maxErrors ?? '—'}</span>
                  </dd>
                </div>
              </dl>
            </div>
          )}
          {children}
        </main>
        <footer className="border-t px-4 py-5 text-center text-[11px]" style={{ borderColor: 'var(--line)', color: 'var(--text-faint)' }}>
          {locale === 'pl'
            ? 'Dane: Leaguepedia · Projekt fanowski, niezwiązany z Riot Games'
            : 'Data: Leaguepedia · Fan project, not affiliated with Riot Games'}
          {' · Made by '}
          <a href="https://x.com/AxwordLol" target="_blank" rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-[var(--text)]">Axword</a>
        </footer>
      </div>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
