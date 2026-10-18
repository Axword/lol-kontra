'use client'
import GameLayout from '@/components/layout/GameLayout'
import ArchiveList from '@/components/archive/ArchiveList'
import { usePrefs } from '@/lib/store'

export default function ArchivePage() {
  const locale = usePrefs((s) => s.locale)

  return (
    <GameLayout>
      <div className="mx-auto w-full max-w-5xl space-y-7">
        <header className="space-y-2">
          <h1 className="text-[28px] font-semibold leading-tight sm:text-[32px]">{locale === 'pl' ? 'Archiwum' : 'Archive'}</h1>
          <p className="max-w-2xl text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
            {locale === 'pl'
              ? 'Wróć do wcześniejszych plansz, swoich składów i wyników. Gry z archiwum liczą się do rankingu.'
              : 'Revisit earlier boards, your lineups and scores. Archived games count towards the leaderboard.'}
          </p>
        </header>
        <ArchiveList />
      </div>
    </GameLayout>
  )
}
