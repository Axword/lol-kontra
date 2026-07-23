'use client'
import { useDailyTodayCompat } from '@/lib/api'
import GameView from '@/components/game/GameView'

export default function HomePage() {
  const { data, isLoading, error } = useDailyTodayCompat()
  return <GameView daily={data} isLoading={isLoading} error={error} showArchive />
}
