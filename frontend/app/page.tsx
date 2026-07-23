'use client'
import { useDailyToday } from '@/lib/api'
import GameView from '@/components/game/GameView'

export default function HomePage() {
  const { data, isLoading, error } = useDailyToday()
  return <GameView daily={data} isLoading={isLoading} error={error} showArchive />
}
