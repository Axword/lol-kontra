'use client'
import { Daily, DailySlot, useSubmitAnswer, useMySubmission } from '@/lib/api'
import { useRosterStore } from '@/lib/store'
import { useEffect, useState, useRef } from 'react'
import RiftBoard from './RiftBoard'
import PlayerPickerModal from './PlayerPickerModal'
import { sound } from '@/lib/sound'

export default function RosterBoard({ daily, onScore }: { daily: Daily, onScore?: (total:number, answers:any[])=>void }) {
  const { picks, setDaily, setAnswer, incrementError, errors, maxErrors, guestToken, reset } = useRosterStore()
  const submitAnswer = useSubmitAnswer()
  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [verifyingSlot, setVerifyingSlot] = useState<number | null>(null)
  const [toast, setToast] = useState<string>('')
  const inFlight = useRef<Set<number>>(new Set())

  useEffect(() => {
    setDaily(daily.id)
  }, [daily.id, setDaily])

  // hydrate from server (previous answers)
  const mySub = useMySubmission(daily.id, guestToken)
  useEffect(() => {
    if (mySub.data?.answers) {
      mySub.data.answers.forEach((a:any) => {
        const slotId = a.daily_slot
        const existing = picks[slotId]
        if (!existing?.locked || existing.is_correct !== true) {
          setAnswer(slotId, {
            is_correct: a.is_correct,
            rarity_tier: a.rarity_tier,
            points_awarded: a.points_awarded,   // deduction
            pick_percent: a.pick_percent || a.rarity_percent,
            is_diamond_pick: a.is_diamond_pick,
            locked: !!a.is_correct,
          })
          // ensure player
          const store = useRosterStore.getState()
          const p = store.picks[slotId]
          if (!p?.playerSlug) {
            useRosterStore.setState(s => ({
              picks: {
                ...s.picks,
                [slotId]: {
                  ...(s.picks[slotId] || { slotId }),
                  playerSlug: a.player_slug,
                  playerNickname: a.player_nickname,
                  is_correct: a.is_correct,
                  rarity_tier: a.rarity_tier,
                  points_awarded: a.points_awarded,
                  pick_percent: a.pick_percent || a.rarity_percent,
                  is_diamond_pick: a.is_diamond_pick,
                  locked: !!a.is_correct
                }
              }
            }))
          }
        }
      })
      if (onScore && mySub.data.total_points != null) {
        onScore(mySub.data.total_points, mySub.data.answers)
      }
    }
  }, [mySub.data])

  // AUTO per-slot verification – as soon as pick is made
  useEffect(() => {
    daily.slots.forEach(slot => {
      const pick = picks[slot.id]
      if (!pick?.playerSlug) return
      if (pick.locked && pick.is_correct === true) return
      if (inFlight.current.has(slot.id)) return

      inFlight.current.add(slot.id)
      setVerifyingSlot(slot.id)
      sound.submit()

      const gToken = guestToken || (typeof window !== 'undefined' ? localStorage.getItem('guest_token') || '' : '')

      submitAnswer.mutate({
        daily_id: daily.id,
        slot_id: slot.id,
        player_slug: pick.playerSlug!,
        guest_token: gToken,
      }, {
        onSuccess: (data: any) => {
          inFlight.current.delete(slot.id)
          setVerifyingSlot(null)

          const isCorrect = !!data.is_correct
          const deduction = data.deduction ?? data.points_awarded ?? 0
          const pickP = data.pick_percent ?? data.rarity_percent ?? 0

          setAnswer(slot.id, {
            is_correct: isCorrect,
            rarity_tier: data.rarity_tier,
            points_awarded: deduction,
            pick_percent: pickP,
            is_diamond_pick: data.is_diamond_pick,
            locked: isCorrect,
          })

          if (isCorrect) {
            if (data.is_diamond_pick) sound.diamond()
            else sound.success()
          } else {
            sound.error()
            incrementError()
          }

          const nick = pick.playerNickname
          const pct = pickP.toFixed(1)
          const msg = `${slot.role.toUpperCase()} • ${nick} → ${isCorrect ? '✓' : '✗'}  ${pct}%  ${isCorrect ? '-' : ''}${deduction}${data.is_diamond_pick ? ' 💎' : ''}`

          setToast(msg)
          setTimeout(() => setToast(''), 2800)

          if (data.total_points != null && onScore) {
            onScore(data.total_points, [data])
          }
        },
        onError: (e: any) => {
          inFlight.current.delete(slot.id)
          setVerifyingSlot(null)
          sound.error()
          mySub.refetch()
        }
      })
    })
  }, [picks, daily.id, daily.slots])

  const filled = daily.slots.filter(s => picks[s.id]?.playerSlug).length
  const lockedCorrect = daily.slots.filter(s => picks[s.id]?.is_correct === true).length
  const totalDeduction = daily.slots.reduce((sum, s) => sum + (picks[s.id]?.points_awarded || 0), 0)
  const remainingScore = Math.round((500 - totalDeduction) * 10) / 10
  const gameOver = errors >= maxErrors

  const handlePick = (slot: DailySlot) => {
    const p = picks[slot.id]
    if (p?.locked && p.is_correct === true) {
      sound.error()
      setToast(`${slot.role.toUpperCase()} ZABLOKOWANE → ${p.playerNickname} ✓`)
      setTimeout(() => setToast(''), 1600)
      return
    }
    if (gameOver) {
      setToast('KONIEC – 10 błędów')
      setTimeout(() => setToast(''), 1400)
      return
    }
    sound.open()
    setPickerSlot(slot)
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
        onPick={handlePick}
        disabled={gameOver}
      />

      {/* KONTRA STATUS BAR – NO SUBMIT BUTTON */}
      <div className="bg-[#0f141b] border border-zinc-800 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="flex items-center gap-5 flex-wrap">
          <span className="font-semibold text-[#C89B3C]">
            Wynik: <b className="text-white text-[15px]">{remainingScore}</b> / 500
          </span>
          <span className="text-red-400">
            Odjęto: <b>-{totalDeduction.toFixed(1)}</b>
          </span>
          <span className="text-zinc-400">
            Trafienia: <b className={lockedCorrect > 0 ? "text-emerald-400" : "text-white"}>{lockedCorrect}/5</b>
          </span>
          <span className={errors >= 8 ? "text-red-500 font-bold" : errors > 0 ? "text-red-400" : "text-zinc-400"}>
            Błędy: <b>{errors}/{maxErrors}</b>
          </span>
          {verifyingSlot && (
            <span className="text-amber-300 animate-pulse">⏳ Weryfikuję {daily.slots.find(s => s.id === verifyingSlot)?.role}…</span>
          )}
          {toast && <span className="text-[#C89B3C] font-medium">{toast}</span>}
          {gameOver && <span className="text-red-500 font-bold">✗ KONIEC GRY</span>}
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-zinc-500">1 próba dziennie • retry do skutku • max 10 błędów</span>
          <button
            onClick={() => { if (confirm('Zresetować?')) reset() }}
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
            const isLockedCorrect = p?.is_correct === true
            const isWrong = p?.is_correct === false
            const color = isLockedCorrect
              ? 'text-emerald-400 border-emerald-700/40 bg-emerald-950/20'
              : isWrong
                ? 'text-red-400 border-red-800/40 bg-red-950/20'
                : p?.playerSlug
                  ? 'text-amber-300 border-amber-700/40 bg-amber-950/10'
                  : 'text-zinc-500 border-zinc-800 bg-[#10161f]'

            return (
              <div key={s.id} className={`rounded-lg border px-2 py-2 ${color}`}>
                <div className="text-[10px] uppercase opacity-80">{s.role}</div>
                <div className="truncate font-semibold">{p?.playerNickname || '—'}</div>
                <div className="text-[11px] mt-0.5">
                  {p?.locked && isLockedCorrect ? (
                    <>{p.pick_percent?.toFixed(1) || '0'}% → -{p.points_awarded} {p.is_diamond_pick ? '💎' : ''}</>
                  ) : isWrong ? (
                    '✗ spróbuj ponownie…'
                  ) : p?.playerSlug ? (
                    '⏳ weryfikacja…'
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
        <span className="ml-auto">start 500 • niższy wynik = lepszy</span>
      </div>

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        onClose={() => { sound.close(); setPickerSlot(null) }}
      />
    </div>
  )
}
