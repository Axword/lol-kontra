'use client'
import { Daily, DailySlot, useSubmitAnswer, useMySubmission } from '@/lib/api'
import { useRosterStore } from '@/lib/store'
import { useEffect, useState, useRef } from 'react'
import RiftBoard from './RiftBoard'
import PlayerPickerModal from './PlayerPickerModal'
import { sound } from '@/lib/sound'

export default function RosterBoard({ daily, onScore }: { daily: Daily, onScore?: (total:number, answers:any[])=>void }) {
  const { picks, setDaily, setAnswer, guestToken, reset } = useRosterStore()
  const submitAnswer = useSubmitAnswer()
  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [verifyingSlot, setVerifyingSlot] = useState<number | null>(null)
  const [toast, setToast] = useState<string>('')
  const inFlight = useRef<Set<number>>(new Set())

  useEffect(() => {
    setDaily(daily.id)
  }, [daily.id, setDaily])

  // hydrate from server – lock already answered slots
  const mySub = useMySubmission(daily.id, guestToken)
  useEffect(() => {
    if (mySub.data?.answers) {
      mySub.data.answers.forEach((a:any) => {
        const slotId = a.daily_slot
        const existing = picks[slotId]
        if (!existing?.locked) {
          // @ts-ignore – setPick not exposed here, use setAnswer which also stores player info
          setAnswer(slotId, {
            is_correct: a.is_correct,
            rarity_tier: a.rarity_tier,
            points_awarded: a.points_awarded,
            is_diamond_pick: a.is_diamond_pick,
            locked: true,
          })
          // also ensure player info is stored
          const store = useRosterStore.getState()
          const p = store.picks[slotId]
          if (!p?.playerSlug) {
            // inject player info
            useRosterStore.setState(s => ({
              picks: { ...s.picks, [slotId]: { ...(s.picks[slotId]||{slotId}), playerSlug: a.player_slug, playerNickname: a.player_nickname, is_correct: a.is_correct, rarity_tier: a.rarity_tier, points_awarded: a.points_awarded, is_diamond_pick: a.is_diamond_pick, locked: true } }
            }))
          }
        }
      })
      if (onScore && mySub.data.total_points != null) {
        onScore(mySub.data.total_points, mySub.data.answers)
      }
    }
  }, [mySub.data])

  // PER-SLOT INSTANT verification
  useEffect(() => {
    daily.slots.forEach(slot => {
      const pick = picks[slot.id]
      if (!pick?.playerSlug) return
      if (pick.locked) return
      if (inFlight.current.has(slot.id)) return
      // fire verification
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
        onSuccess: (data:any) => {
          inFlight.current.delete(slot.id)
          setVerifyingSlot(null)
          setAnswer(slot.id, {
            is_correct: data.is_correct,
            rarity_tier: data.rarity_tier,
            points_awarded: data.points_awarded,
            is_diamond_pick: data.is_diamond_pick,
            locked: true,
          })
          if (data.is_correct) {
            if (data.is_diamond_pick) sound.diamond()
            else sound.success()
          } else {
            sound.error()
          }
          const pts = data.points_awarded || 0
          const tier = data.rarity_tier || '—'
          setToast(`${slot.role.toUpperCase()} • ${pick.playerNickname} → ${data.is_correct ? '✓' : '✗'}  ${tier}  ${pts}pkt${data.is_diamond_pick ? ' 💎' : ''}`)
          setTimeout(()=>setToast(''), 2600)
          // update total score callback
          if (data.total_points != null && onScore) {
            // fetch full answers? use mySub refetch
            mySub.refetch()
          }
        },
        onError: (e:any) => {
          inFlight.current.delete(slot.id)
          setVerifyingSlot(null)
          sound.error()
          // if slot already locked server-side, hydrate
          mySub.refetch()
        }
      })
    })
  }, [picks, daily.id, daily.slots])

  const filled = daily.slots.filter(s => picks[s.id]?.playerSlug).length
  const locked = daily.slots.filter(s => picks[s.id]?.locked).length
  const correct = daily.slots.filter(s => picks[s.id]?.is_correct).length
  const totalPoints = daily.slots.reduce((sum, s) => sum + (picks[s.id]?.points_awarded || 0), 0)

  const handlePick = (slot: DailySlot) => {
    const p = picks[slot.id]
    if (p?.locked) {
      // show result again, no change allowed
      sound.error()
      setToast(`${slot.role.toUpperCase()} ZABLOKOWANE → ${p.playerNickname} ${p.is_correct ? '✓' : '✗'} ${p.points_awarded||0}pkt`)
      setTimeout(()=>setToast(''), 1800)
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
        disabled={false}
      />

      {/* status – per slot instant */}
      <div className="bg-[#0f141b] border border-zinc-800 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="flex items-center gap-5 flex-wrap">
          <span className="text-zinc-400">
            Zablokowano: <b className="text-white">{locked}/5</b>
          </span>
          <span className="text-zinc-400">
            Trafienia: <b className={correct>0 ? "text-emerald-400":"text-white"}>{correct}/5</b>
          </span>
          <span className="text-zinc-400">
            Punkty: <b className="text-[#C89B3C]">{totalPoints}</b>
          </span>
          {verifyingSlot && (
            <span className="text-amber-300 animate-pulse">⏳ Weryfikuję {daily.slots.find(s=>s.id===verifyingSlot)?.role}…</span>
          )}
          {toast && (
            <span className="text-[#C89B3C] font-medium">{toast}</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-zinc-500">1 próba / slot • wynik natychmiast</span>
          {locked>0 && (
            <button
              onClick={()=> { if(confirm('Zresetować lokalnie? Zablokowane sloty wrócą po odświeżeniu z serwera.')) { reset(); } }}
              className="px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-white"
            >reset lokalny</button>
          )}
        </div>
      </div>

      {/* per-slot results list */}
      <div className="bg-[#0b1218] border border-zinc-800 rounded-2xl p-3">
        <div className="text-[11px] text-zinc-400 mb-2">WYNIKI LIVE — kliknij rolę by wybrać (po wyborze slot jest blokowany):</div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-[12px] font-mono">
          {daily.slots.map(s => {
            const p = picks[s.id]
            const state = !p?.playerSlug ? 'empty' : p.locked ? (p.is_correct ? 'ok' : 'bad') : 'pending'
            const color = state==='ok' ? 'text-emerald-400 border-emerald-700/40 bg-emerald-950/20'
              : state==='bad' ? 'text-red-400 border-red-800/40 bg-red-950/20'
              : state==='pending' ? 'text-amber-300 border-amber-700/40 bg-amber-950/10'
              : 'text-zinc-500 border-zinc-800 bg-[#10161f]'
            return (
              <div key={s.id} className={`rounded-lg border px-2 py-2 ${color}`}>
                <div className="text-[10px] uppercase opacity-80">{s.role}</div>
                <div className="truncate font-semibold">{p?.playerNickname || '—'}</div>
                <div className="text-[11px] mt-0.5">
                  {p?.locked ? (
                    <>{p.is_correct ? '✓' : '✗'} {p.rarity_tier || '—'} {p.points_awarded||0}pkt {p.is_diamond_pick ? '💎':''}</>
                  ) : p?.playerSlug ? '⏳…' : 'wybierz'}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="text-[11px] text-zinc-500 flex flex-wrap gap-x-4 gap-y-1 px-1">
        <span>Common <b className="text-zinc-300">10</b></span>
        <span className="text-[#60a5fa]">Rare <b>25</b></span>
        <span className="text-[#c084fc]">Epic <b>60</b></span>
        <span className="text-[#fbbf24]">Legendary <b>120</b></span>
        <span className="text-[#22d3ee]">💎 <b>+50</b></span>
        <span className="ml-auto">slot blokowany po wyborze • nie można zmienić</span>
      </div>

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        onClose={()=>{ sound.close(); setPickerSlot(null)}}
      />
    </div>
  )
}
