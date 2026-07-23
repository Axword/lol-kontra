'use client'
import { useParams, useRouter } from 'next/navigation'
import { useDaily } from '@/lib/api'
import GameView from '@/components/game/GameView'

export default function DailyIdPage() {
  const params = useParams()
  const router = useRouter()
  const id = Number(params?.id)

  const { data, isLoading, error } = useDaily(Number.isFinite(id) ? id : undefined)

  return (
    <GameView
      daily={data}
      isLoading={isLoading}
      error={error}
      showArchive
      backLink={
        <button onClick={() => router.push('/')} className="text-muted hover:text-ink text-[12px] transition-colors">
          ← Dzisiejsza
        </button>
      }
    />
  )
}
