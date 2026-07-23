'use client'
import { Daily, DailySlot, MAX_ERRORS, START_SCORE, verifyPick } from '@/lib/api'
import { useGame, useGameStore } from '@/lib/store'
import { useState } from 'react'
import RiftBoard from './RiftBoard'
import PlayerPickerModal from './PlayerPickerModal'
import { sound } from '@/lib/sound'

export default function RosterBoard({ daily }: { daily: Daily }) {
  const game = useGame(daily.id)
  const applyPick = useGameStore(s => s.applyPick)
  const clearPick = useGameStore(s => s.clearPick)
  const resetGame = useGameStore(s => s.resetGame)
  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [toast, setToast] = useState<string>('')

  const picks = game.picks
  const lockedCorrect = daily.slots.filter(s => picks[s.id]?.is_correct === true).length
  const totalDeduction = daily.slots.reduce((sum, s) => {
    const p = picks[s.id]
    return sum + (p?.is_correct ? p.deduction : 0)
  }, 0)
  const remainingScore = Math.round((START_SCORE - totalDeduction) * 10) / 10
  const gameOver = game.errors >= MAX_ERRORS
  const gameWon = lockedCorrect >= daily.slots.length && daily.slots.length > 0

  const handlePick = (slot: DailySlot) => {
    const p = picks[slot.id]
    if (p?.locked && p.is_correct) {
      sound.error()
      setToast(`${slot.role.toUpperCase()} ZABLOKOWANE → ${p.playerNickname} ✓`)
      setTimeout(() => setToast(''), 1600)
      return
    }
    if (gameOver) {
      setToast(`KONIEC – ${MAX_ERRORS} błędów`)
      setTimeout(() => setToast(''), 1400)
      return
    }
    sound.open()
    setPickerSlot(slot)
  }

  const handleSelect = (slot: DailySlot, slug: string, nickname: string) => {
    const result = verifyPick(slot, slug)
    applyPick(daily.id, {
      slotId: slot.id,
      playerSlug: slug,
      playerNickname: nickname,
      is_correct: result.is_correct,
      rarity_tier: result.rarity_tier,
      deduction: result.deduction,
      pick_percent: result.pick_percent,
      is_diamond_pick: result.is_diamond_pick,
      locked: result.is_correct,
    }, daily.slots.length, daily.date)

    if (result.is_correct) {
      if (result.is_diamond_pick) sound.diamond()
      else sound.success()
    } else {
      sound.error()
    }

    const msg = `${slot.role.toUpperCase()} • ${nickname} → ${result.is_correct ? '✓' : '✗'}  ${result.pick_percent.toFixed(1)}%  ${result.is_correct ? `-${result.deduction}` : ''}${result.is_diamond_pick ? ' ◆' : ''}`
    setToast(msg)
    setTimeout(() => setToast(''), 2800)
  }

  if (!daily.slots || daily.slots.length === 0) {
    return (
      <div className="bg-panel border border-line rounded-console text-center py-10 px-4">
        <div className="text-warn font-semibold mb-1">Brak slotów w tym Daily</div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Role cards with conditions */}
      <RiftBoard
        slots={daily.slots}
        picks={picks}
        onPick={handlePick}
        onClear={(slotId) => clearPick(daily.id, slotId)}
        disabled={gameOver}
      />

      {/* Compact status bar */}
      <div className="bg-panel border border-line rounded-console px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-[12px]">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="font-semibold text-ink">
            Wynik: <b className="text-[14px] mono text-accent">{remainingScore}</b> <span className="text-muted font-normal">/ {START_SCORE}</span>
          </span>
          <span className="text-muted">
            Trafione: <b className={lockedCorrect > 0 ? "text-warn" : "text-ink"}>{lockedCorrect}/{daily.slots.length}</b>
          </span>
          <span className={game.errors >= 8 ? "text-red font-bold" : game.errors > 0 ? "text-red" : "text-muted"}>
            Błędy: <b>{game.errors}/{MAX_ERRORS}</b>
          </span>
          {toast && <span className="text-accent font-medium text-[11px]">{toast}</span>}
          {gameOver && <span className="text-red font-bold text-[12px]">✗ KONIEC GRY</span>}
          {gameWon && <span className="text-warn font-bold text-[12px]">KOMPLET!</span>}
        </div>
        <button
          onClick={() => { if (confirm('Zresetować grę dla tego dnia?')) resetGame(daily.id) }}
          className="px-2.5 py-1 rounded-control border border-line text-muted hover:text-ink hover:border-muted text-[11px] transition-colors"
        >
          reset
        </button>
      </div>

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        currentPick={pickerSlot ? picks[pickerSlot.id] : undefined}
        onSelect={(slug, nickname) => {
          if (pickerSlot) handleSelect(pickerSlot, slug, nickname)
          setPickerSlot(null)
        }}
        onClose={() => { sound.close(); setPickerSlot(null) }}
      />
    </div>
  )
}
