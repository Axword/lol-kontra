'use client'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { api, Daily } from '@/lib/api'
import GameLayout from '@/components/layout/GameLayout'
import RosterBoard from '@/components/roster/RosterBoard'
import ArchiveList from '@/components/archive/ArchiveList'
import { useRosterStore } from '@/lib/store'
import Link from 'next/link'

export default function DailyIdPage() {
  const params = useParams()
  const id = params?.id as string
  const errors = useRosterStore(s => s.errors)
  const maxErrors = useRosterStore(s => s.maxErrors)

  const { data, isLoading, error } = useQuery<Daily>({
    queryKey: ['daily', id],
    queryFn: async () => (await api.get(`/dailies/${id}/`)).data,
    enabled: !!id,
  })

  return (
    <GameLayout errorsLeft={maxErrors - errors}>
      {!id || isLoading ? (
        <div className="text-center py-24 text-zinc-500 text-sm">Ładowanie…</div>
      ) : error || !data ? (
        <div className="text-center py-20 text-sm space-y-3">
          <div className="text-red-400">Nie znaleziono Daily #{id}</div>
          <Link href="/" className="text-[#C89B3C] hover:underline">Wróć do dzisiejszego →</Link>
        </div>
      ) : (
        <div className="space-y-8">
          <RosterBoard daily={data} />
          <ArchiveList currentId={data.id} />
        </div>
      )}
    </GameLayout>
  )
}
