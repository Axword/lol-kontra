'use client'
import { useState, useEffect, useMemo } from 'react'
import { usePlayerSearch, usePlayerAutocomplete, Player, DailySlot } from '@/lib/api'
import { countryFlag, roleIcons } from '@/lib/flags'
import { useRosterStore } from '@/lib/store'
import { sound } from '@/lib/sound'

// Extract just the ingame nick from "Nick (Real Name)" format
function extractNick(nickname: string): string {
  const m = nickname.match(/^([^(]+)/)
  return m ? m[1].trim() : nickname
}

// Get real name – from real_name field or from parens in nickname
function extractRealName(p: Player): string {
  if (p.real_name) return p.real_name
  const m = p.nickname.match(/\(([^)]+)\)/)
  return m ? m[1].trim() : ''
}

export default function PlayerPickerModal({
  slot,
  open,
  onClose,
}: {
  slot: DailySlot | null,
  open: boolean,
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const setPick = useRosterStore(s => s.setPick)
  const picks = useRosterStore(s => s.picks)

  // reset query when opening different slot
  useEffect(() => { if(open) setQ('') }, [open, slot?.id])

  // use autocomplete for fast, fallback to full search
  const ac = usePlayerAutocomplete(q.length >= 1 ? q : '')
  const full = usePlayerSearch(q, slot?.role)

  const list: Player[] = useMemo(() => {
    if (q.length === 0) return []
    return (ac.data && ac.data.length ? ac.data : (full.data || [])) as Player[]
  }, [q, ac.data, full.data])

  // close on ESC
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if(e.key==='Escape') onClose() }
    if(open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open || !slot) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg mx-4 bg-[#0f141b] border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* header */}
        <div className="px-5 py-4 border-b border-zinc-800 flex items-center justify-between bg-[#111822]">
          <div>
            <div className="text-xs text-lol-muted uppercase tracking-wider font-semibold">
              {roleIcons[slot.role]} {slot.role.toUpperCase()}
            </div>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {slot.conditions.map(c=>(
                <span key={c.id} className="text-[11px] px-2 py-0.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-300">{c.label_pl}</span>
              ))}
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-white text-xl px-2">×</button>
        </div>

        {/* search */}
        <div className="p-4 border-b border-zinc-800">
          <input
            autoFocus
            value={q}
            onChange={e=>setQ(e.target.value)}
            placeholder="Szukaj: Faker, Caps, Jankos…"
            className="w-full bg-black/40 border border-zinc-700 rounded-xl px-4 py-3 outline-none focus:border-lol-gold text-base"
          />
        </div>

        {/* list */}
        <div className="max-h-[55vh] overflow-y-auto">
          {list.length === 0 && q.length > 0 && !ac.isLoading && !full.isLoading && (
            <div className="p-6 text-center text-zinc-500">Brak wyników</div>
          )}
          {list.length === 0 && q.length === 0 && (
            <div className="p-8 text-center text-zinc-600 text-sm">Szukaj gracza…</div>
          )}
          <ul className="divide-y divide-zinc-900">
            {list.map(p => (
              <li key={p.slug}>
                <button
                  onClick={() => { sound.pick(); setPick(slot.id, p.slug, p.nickname); onClose() }}
                  className="w-full text-left px-4 py-3 hover:bg-zinc-900/80 flex items-center gap-3 transition"
                >
                  {/* FLAG as emoji – big */}
                  <div className="text-3xl w-10 text-center leading-none select-none">
                    {countryFlag(p.country_code)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-white">{extractNick(p.nickname)}</div>
                    {extractRealName(p) && (
                      <div className="text-xs text-zinc-400 truncate">{extractRealName(p)}</div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          {(ac.isLoading || full.isLoading) && q.length > 0 && (
            <div className="p-4 text-center text-zinc-500 text-sm">…</div>
          )}
        </div>

        {/* footer */}
        <div className="px-4 py-2 border-t border-zinc-800 bg-[#0f141b] text-[11px] text-zinc-600 text-right">
          ESC zamknij
        </div>
      </div>
    </div>
  )
}
