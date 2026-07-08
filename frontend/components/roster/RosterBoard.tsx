'use client'
import { Daily, DailySlot } from '@/lib/api'
import { useRosterStore } from '@/lib/store'
import { useSubmitRoster } from '@/lib/api'
import { useEffect, useState, useRef } from 'react'
import RiftBoard from './RiftBoard'
import PlayerPickerModal from './PlayerPickerModal'
import { sound } from '@/lib/sound'

export default function RosterBoard({ daily, onScore }: { daily: Daily, onScore?: (total:number, answers:any[])=>void }) {
  const { picks, setDaily, markSubmitted, submitted, guestToken, reset, clearPick } = useRosterStore()
  const submit = useSubmitRoster()
  const [msg, setMsg] = useState<string>('')
  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [autoCountdown, setAutoCountdown] = useState<number | null>(null)
  const autoTimer = useRef<any>(null)

  useEffect(() => {
    setDaily(daily.id)
  }, [daily.id, setDaily])

  const filled = daily.slots.filter(s => picks[s.id]?.playerSlug).length
  const allFilled = filled === daily.slots.length && daily.slots.length === 5

  // --- AUTO-SUBMIT when 5 picks are ready ---
  useEffect(() => {
    if (submitted || !allFilled || submit.isPending) {
      if (autoTimer.current) { clearTimeout(autoTimer.current); clearInterval(autoTimer.current) }
      setAutoCountdown(null)
      return
    }
    // start 1.2s countdown – gives a moment to change pick if misclick
    let left = 3
    setAutoCountdown(left)
    sound.pick()
    const iv = setInterval(() => {
      left -= 1
      setAutoCountdown(left > 0 ? left : 0)
      if (left <= 0) clearInterval(iv)
    }, 300)
    autoTimer.current = setTimeout(() => {
      handleSubmit()
    }, 1100)
    return () => {
      clearTimeout(autoTimer.current)
      clearInterval(iv)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filled, allFilled, submitted])

  const handleSubmit = async (skipConfirm = true) => {
    if (submitted) return
    if (!allFilled) return
    // ensure guest_token
    let gToken = guestToken
    if (!gToken) {
      gToken = (typeof window !== 'undefined' && localStorage.getItem('guest_token')) ||
               Math.random().toString(36).slice(2) + Date.now().toString(36)
      if (typeof window !== 'undefined') localStorage.setItem('guest_token', gToken)
    }
    const answers = daily.slots.map(s => {
      const pick = picks[s.id]
      if (!pick?.playerSlug) throw new Error('empty slot')
      return { slot_id: s.id, player_slug: pick.playerSlug }
    })
    try {
      sound.submit()
      const res = await submit.mutateAsync({ daily_id: daily.id, guest_token: gToken, answers })
      markSubmitted()
      const total = res?.total_points ?? 0
      const ans = res?.answers || []
      // sounds per answer
      let correctCount = 0
      ans.forEach((a:any, idx:number) => {
        setTimeout(() => {
          if (a.is_correct) {
            correctCount++
            if (a.is_diamond_pick) { sound.diamond() }
            else sound.success()
          } else {
            sound.error()
          }
        }, idx * 280)
      })
      if (onScore) onScore(total, ans)
      // pretty summary
      const summary = ans.map((a:any) =>
        `${(a.slot_role||'').toUpperCase().padEnd(7)} ${a.player_nickname?.padEnd(14,' ')}  ${a.is_correct ? '✓' : '✗'}  ${a.rarity_tier||'-'}  ${a.points_awarded||0}pkt${a.is_diamond_pick?' 💎':''}`
      ).join('\n')
      setMsg(`WYNIK: ${total} pkt  •  ${ans.filter((a:any)=>a.is_correct).length}/5 poprawnych\n\n${summary}`)
      setTimeout(()=> window.scrollTo({top: 520, behavior:'smooth'}), 400)
    } catch (e:any) {
      const data = e?.response?.data
      let txt = 'Błąd wysyłania'
      if (data) {
        if (typeof data === 'string') txt = data
        else if (data.detail) txt = data.detail
        else txt = JSON.stringify(data, null, 2)
      }
      // if already submitted – mark locally
      if (JSON.stringify(data).includes('Już wysłałeś')) {
        markSubmitted()
        txt = 'Ten skład był już wysłany – zobacz wyniki poniżej.'
      }
      setMsg(txt)
      sound.error()
    } finally {
      setAutoCountdown(null)
    }
  }

  // cancel auto-submit if user changes a pick during countdown
  const handlePick = (slot: DailySlot) => {
    if (submitted) return
    if (autoTimer.current) {
      clearTimeout(autoTimer.current)
      setAutoCountdown(null)
    }
    sound.open()
    setPickerSlot(slot)
  }

  if (!daily.slots || daily.slots.length === 0) {
    return (
      <div className="bg-[#0f141b] border border-amber-900/30 rounded-2xl text-center py-10 px-4">
        <div className="text-amber-400 font-semibold mb-1">Brak slotów w tym Daily</div>
        <div className="text-[13px] text-zinc-400">
          Uruchom:<br/>
          <code className="text-[11px] bg-black px-2 py-1 rounded">docker compose exec api python manage.py create_daily --publish</code>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* MAP */}
      <RiftBoard
        slots={daily.slots}
        onPick={handlePick}
        disabled={submitted}
      />

      {/* status bar – NO submit button anymore */}
      <div className="bg-[#0f141b] border border-zinc-800 rounded-2xl px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-[13px]">
        <div className="flex items-center gap-4">
          <span className="text-zinc-400">
            Wypełniono: <b className="text-white text-[15px]">{filled}/5</b>
          </span>
          {submitted && <span className="text-[#C89B3C] font-semibold">✓ Skład wysłany – wynik poniżej</span>}
          {!submitted && allFilled && autoCountdown !== null && (
            <span className="text-amber-300 font-semibold animate-pulse">
              Weryfikuję… {autoCountdown > 0 ? autoCountdown : '✓'}
            </span>
          )}
          {!submitted && !allFilled && (
            <span className="text-zinc-400">Wybierz pozycje na mapie by zgadywać →</span>
          )}
          {submit.isPending && <span className="text-[#C89B3C]">⏳ Wysyłam…</span>}
        </div>

        <div className="flex items-center gap-2">
          {!submitted && filled > 0 && (
            <button
              onClick={()=>{ reset(); setMsg(''); sound.close() }}
              className="text-[11px] px-3 py-1.5 rounded-full border border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white"
            >
              Wyczyść
            </button>
          )}
          {allFilled && !submitted && !submit.isPending && (
            <div className="text-[11px] text-amber-300">Auto-wysyłka…</div>
          )}
          {submitted && (
            <a href={`#results`} className="text-[11px] text-[#C89B3C] hover:underline">↓ wyniki</a>
          )}
        </div>
      </div>

      {/* inline result summary – appears immediately after submit */}
      {msg && (
        <div id="results" className="bg-[#0b1218] border border-[#C89B3C]/25 rounded-2xl p-4 shadow-[0_0_24px_rgba(200,155,60,0.08)]">
          <pre className="text-[12px] leading-relaxed whitespace-pre-wrap font-mono text-zinc-200">{msg}</pre>
          <div className="mt-3 text-[11px] text-zinc-400">
            Kliknij dowolną rolę na mapie powyżej aby zobaczyć szczegółowy rozkład % dla tej pozycji →
            <a href={`/results/${daily.id}`} className="ml-2 text-[#C89B3C] hover:underline">pełne wyniki</a>
          </div>
        </div>
      )}

      {/* legend – compact */}
      <div className="text-[11px] text-zinc-500 flex flex-wrap gap-x-4 gap-y-1 px-1">
        <span>Common <b className="text-zinc-300">10</b></span>
        <span className="text-[#60a5fa]">Rare <b>25</b></span>
        <span className="text-[#c084fc]">Epic <b>60</b></span>
        <span className="text-[#fbbf24]">Legendary <b>120</b></span>
        <span className="text-[#22d3ee]">💎 <b>+50</b></span>
        <span className="ml-auto text-zinc-500">1 próba / dzień • wynik natychmiast</span>
      </div>

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        onClose={()=>{ sound.close(); setPickerSlot(null)}}
      />
    </div>
  )
}
