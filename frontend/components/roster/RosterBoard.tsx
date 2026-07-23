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

  // lokalna weryfikacja – natychmiast, bez API
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

    const msg = `${slot.role.toUpperCase()} • ${nickname} → ${result.is_correct ? '✓' : '✗'}  ${result.pick_percent.toFixed(1)}%  ${result.is_correct ? `-${result.deduction}` : ''}${result.is_diamond_pick ? ' 💎' : ''}`
    setToast(msg)
    setTimeout(() => setToast(''), 2800)
  }

  if (!daily.slots || daily.slots.length === 0) {
    return (
      <div className="bg-[#0f141b] border border-amber-900/30 rounded-2xl text-center py-10 px-4">
        <div className="text-amber-400 font-semibold mb-1">Brak slotów w tym Daily</div>
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

      {/* KONTRA STATUS BAR */}
      <div className="bg-[#0f141b] border border-zinc-800 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="flex items-center gap-5 flex-wrap">
          <span className="font-semibold text-[#C89B3C]">
            Wynik: <b className="text-white text-[15px]">{remainingScore}</b> / {START_SCORE}
          </span>
          <span className="text-red-400">
            Odjęto: <b>-{totalDeduction.toFixed(1)}</b>
          </span>
          <span className="text-zinc-400">
            Trafienia: <b className={lockedCorrect > 0 ? "text-emerald-400" : "text-white"}>{lockedCorrect}/{daily.slots.length}</b>
          </span>
          <span className={game.errors >= 8 ? "text-red-500 font-bold" : game.errors > 0 ? "text-red-400" : "text-zinc-400"}>
            Błędy: <b>{game.errors}/{MAX_ERRORS}</b>
          </span>
          {toast && <span className="text-[#C89B3C] font-medium">{toast}</span>}
          {gameOver && <span className="text-red-500 font-bold">✗ KONIEC GRY</span>}
          {gameWon && <span className="text-emerald-400 font-bold">🏆 KOMPLET! Wynik: {remainingScore}</span>}
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-zinc-500">weryfikacja natychmiastowa • retry do skutku • max {MAX_ERRORS} błędów</span>
          <button
            onClick={() => { if (confirm('Zresetować grę dla tego dnia?')) resetGame(daily.id) }}
            className="px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-white text-[11px]"
          >
            reset
          </button>
        </div>
      </div>

      {/* LIVE results – kontra style */}
      <div className="bg-[#0b1218] border border-zinc-800 rounded-2xl p-3">
        <div className="text-[11px] text-zinc-400 mb-2">WYNIKI LIVE — kliknij rolę na mapie → wybór = natychmiastowa weryfikacja</div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-[12px] font-mono">
          {daily.slots.map(s => {
            const p = picks[s.id]
            const isCorrect = p?.is_correct === true
            const isWrong = p ? !p.is_correct : false
            const color = isCorrect
              ? 'text-emerald-400 border-emerald-700/40 bg-emerald-950/20'
              : isWrong
                ? 'text-red-400 border-red-800/40 bg-red-950/20'
                : 'text-zinc-500 border-zinc-800 bg-[#10161f]'

            return (
              <div key={s.id} className={`rounded-lg border px-2 py-2 ${color}`}>
                <div className="text-[10px] uppercase opacity-80">{s.role}</div>
                <div className="truncate font-semibold">{p?.playerNickname || '—'}</div>
                <div className="text-[11px] mt-0.5">
                  {isCorrect ? (
                    <>{p!.pick_percent.toFixed(1)}% → -{p!.deduction} {p!.is_diamond_pick ? '💎' : ''}</>
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

      <div className="text-[11px] text-zinc-500 flex flex-wrap gap-x-4 gap-y-1 px-1">
        <span>pick % → strata</span>
        <span className="text-zinc-300">4% → -96</span>
        <span className="text-[#60a5fa]">1% → -99</span>
        <span className="text-[#c084fc]">0.5% → -99.5</span>
        <span className="text-[#fbbf24]">0.1% → -99.9</span>
        <span className="text-[#22d3ee]">💎 -100</span>
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
