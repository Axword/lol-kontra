'use client'
import { useDailyToday } from '@/lib/api'
import RosterBoard from '@/components/roster/RosterBoard'
import GameLayout from '@/components/layout/GameLayout'
import ArchiveList from '@/components/archive/ArchiveList'
import { useRosterStore } from '@/lib/store'
import { useState } from 'react'

export default function HomePage() {
  const { data, isLoading, error, refetch } = useDailyToday()
  const errors = useRosterStore(s => s.errors)
  const maxErrors = useRosterStore(s => s.maxErrors)

  if (isLoading) return (
    <GameLayout errorsLeft={maxErrors - errors}>
      <div className="text-center py-24 text-zinc-500 text-sm">Ładowanie…</div>
    </GameLayout>
  )

  if (error || !data) return (
    <GameLayout errorsLeft={maxErrors - errors}>
      <div className="text-center py-20 text-red-400 text-sm space-y-3">
        <div>Błąd ładowania Daily.</div>
        <button onClick={() => refetch()} className="pill">Spróbuj ponownie</button>
      </div>
    </GameLayout>
  )

  return (
    <GameLayout errorsLeft={maxErrors - errors}>
      <div className="space-y-8">
        <RosterBoard daily={data} />
        <ArchiveList currentId={data.id} />
      </div>
    </GameLayout>
  )
}
