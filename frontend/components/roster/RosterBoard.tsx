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
  const filled = daily.slots.filter(s => picks[s.id]?.playerSlug).length
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
      <RiftBoard
        slots={daily.slots}
        picks={picks}
        onPick={handlePick}
        onClear={(slotId) => clearPick(daily.id, slotId)}
        disabled={gameOver}
      />

      {/* STATUS BAR */}
      <div className="bg-panel border border-line rounded-console px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="flex items-center gap-5 flex-wrap">
          <span className="font-semibold text-ink">
            Wynik: <b className="text-[15px] mono">{remainingScore}</b> <span className="text-muted font-normal">/ {START_SCORE}</span>
          </span>
          <span className="text-red">
            Odjęto: <b>-{totalDeduction.toFixed(1)}</b>
          </span>
          <span className="text-muted">
            Trafienia: <b className={lockedCorrect > 0 ? "text-warn" : "text-ink"}>{lockedCorrect}/{daily.slots.length}</b>
          </span>
          <span className={game.errors >= 8 ? "text-red font-bold" : game.errors > 0 ? "text-red" : "text-muted"}>
            Błędy: <b>{game.errors}/{MAX_ERRORS}</b>
          </span>
          {toast && <span className="text-accent font-medium">{toast}</span>}
          {gameOver && <span className="text-red font-bold">✗ KONIEC GRY</span>}
          {gameWon && <span className="text-warn font-bold">KOMPLET! Wynik: {remainingScore}</span>}
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-muted">weryfikacja natychmiastowa • retry do skutku • max {MAX_ERRORS} błędów</span>
          <button
            onClick={() => { if (confirm('Zresetować grę dla tego dnia?')) resetGame(daily.id) }}
            className="px-2 py-1 rounded-control border border-line text-muted hover:text-ink hover:border-muted text-[11px] transition-colors"
          >
            reset
          </button>
        </div>
      </div>

      {/* LIVE results */}
      <div className="bg-panel border border-line rounded-console p-3">
        <div className="text-[11px] text-muted mb-2">WYNIKI LIVE — kliknij rolę na mapie → wybór = natychmiastowa weryfikacja</div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-[12px] font-mono">
          {daily.slots.map(s => {
            const p = picks[s.id]
            const isCorrect = p?.is_correct === true
            const isWrong = p ? !p.is_correct : false
            const color = isCorrect
              ? 'text-warn border-warn/30 bg-accent-soft'
              : isWrong
                ? 'text-red border-red/30 bg-red/5'
                : 'text-muted border-line bg-bg'

            return (
              <div key={s.id} className={`rounded-control border px-2 py-2 ${color}`}>
                <div className="text-[10px] uppercase opacity-80">{s.role}</div>
                <div className="truncate font-semibold text-ink">{p?.playerNickname || '—'}</div>
                <div className="text-[11px] mt-0.5">
                  {isCorrect ? (
                    <>{p!.pick_percent.toFixed(1)}% → -{p!.deduction} {p!.is_diamond_pick ? '◆' : ''}</>
                  ) : isWrong ? (
                    '✗ spróbuj ponownie…'
                  ) : (
                    'wybierz'
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="text-[11px] text-muted flex flex-wrap gap-x-4 gap-y-1 px-1">
        <span>pick % → strata</span>
        <span className="r-common">4% → -96</span>
        <span className="r-rare">1% → -99</span>
        <span className="r-epic">0.5% → -99.5</span>
        <span className="r-legendary">0.1% → -99.9</span>
        <span className="r-diamond">◆ -100</span>
        <span className="ml-auto">start {START_SCORE} • niższy wynik = lepszy</span>
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
