import { useEffect, useState } from 'react'

/** The game's day follows the server's Warsaw timezone, including DST. */
export function gameDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Warsaw', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now)
  const part = (type: string) => parts.find((p) => p.type === type)!.value
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function useGameDate() {
  const [date, setDate] = useState(() => gameDate())
  useEffect(() => {
    const update = () => setDate(gameDate())
    const timer = setInterval(update, 1_000)
    // Returning from a suspended tab must also switch to the current board.
    window.addEventListener('focus', update)
    return () => { clearInterval(timer); window.removeEventListener('focus', update) }
  }, [])
  return date
}

export function isValidDailyId(id: unknown): id is number {
  return typeof id === 'number' && Number.isSafeInteger(id) && id > 0
}

export function isAvailableDaily(daily: { date: string; status: string }, today = gameDate()) {
  return ['published', 'closed', 'scored'].includes(daily.status) && daily.date <= today
}
