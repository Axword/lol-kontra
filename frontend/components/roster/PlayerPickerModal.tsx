'use client'
import { useState, useEffect, useMemo } from 'react'
import { usePlayers, searchPlayers, Player, DailySlot } from '@/lib/api'
import { countryFlag, countryLabel, roleIcons } from '@/lib/flags'
import { Pick } from '@/lib/store'
import { sound } from '@/lib/sound'

export default function PlayerPickerModal({
  slot,
  open,
  currentPick,
  onSelect,
  onClose,
}: {
  slot: DailySlot | null,
  open: boolean,
  currentPick?: Pick,
  onSelect: (slug: string, nickname: string) => void,
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const { data: players, isLoading } = usePlayers()

  // reset query when opening different slot
  useEffect(() => { if (open) setQ('') }, [open, slot?.id])

  const list: Player[] = useMemo(() => {
    if (!players) return []
    if (q.length === 0) {
      // podpowiedzi – gracze roli slotu, najpierw z największą liczbą Worlds
      const rolePlayers = players
        .filter(p => p.primary_role === slot?.role)
        .sort((a, b) => (b.worlds_count - a.worlds_count) || a.nickname.localeCompare(b.nickname))
      return rolePlayers.slice(0, 30)
    }
    return searchPlayers(players, q)
  }, [q, players, slot?.role])

  // close on ESC
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    if (open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open || !slot) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl mx-4 bg-[#0f141b] border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* header */}
        <div className="px-5 py-4 border-b border-zinc-800 flex items-center justify-between bg-[#111822]">
          <div>
            <div className="text-xs text-lol-muted uppercase tracking-wider">
              {roleIcons[slot.role]} {slot.role.toUpperCase()}
            </div>
            <div className="text-lg font-semibold">Wybierz zawodnika</div>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {slot.conditions.map(c => (
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
            onChange={e => setQ(e.target.value)}
            placeholder="Szukaj: Faker, Caps, Jankos…"
            className="w-full bg-black/40 border border-zinc-700 rounded-xl px-4 py-3 outline-none focus:border-lol-gold text-base"
          />
          <div className="text-[11px] text-zinc-500 mt-2">
            {q ? `Wyniki dla "${q}" — ${list.length}` : `Sugestie dla roli ${slot.role.toUpperCase()} – wpisz nick aby wyszukać w całej bazie.`}
          </div>
        </div>

        {/* list */}
        <div className="max-h-[55vh] overflow-y-auto">
          {currentPick && (
            <div className="px-4 py-2 text-xs text-lol-gold border-b border-zinc-900 bg-amber-950/10">
              Aktualny wybór: <b>{currentPick.playerNickname}</b> – kliknij innego aby zmienić
            </div>
          )}
          {isLoading && <div className="p-4 text-center text-zinc-500 text-sm">Ładowanie bazy graczy…</div>}
          {!isLoading && list.length === 0 && q.length > 0 && (
            <div className="p-6 text-center text-zinc-500">Brak wyników</div>
          )}
          <ul className="divide-y divide-zinc-900">
            {list.map(p => (
              <li key={p.slug}>
                <button
                  onClick={() => { sound.pick(); onSelect(p.slug, p.nickname) }}
                  className="w-full text-left px-4 py-3 hover:bg-zinc-900/80 flex items-center gap-3 transition"
                >
                  <div className="text-2xl w-9 text-center">
                    {countryFlag(p.country_code)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold flex items-center gap-2">
                      {p.nickname}
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 uppercase">{p.primary_role}</span>
                    </div>
                    <div className="text-xs text-zinc-400 truncate">
                      {countryLabel(p.country_code)} • {p.residency} • Worlds: {p.worlds_count}
                      {p.real_name ? ` • ${p.real_name}` : ''}
                    </div>
                  </div>
                  <div className="text-right text-[11px] text-zinc-500">
                    {p.is_active ? <span className="text-emerald-400">● active</span> : <span>retired</span>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* footer */}
        <div className="px-4 py-3 border-t border-zinc-800 bg-[#0f141b] text-[11px] text-zinc-500 flex justify-between">
          <span>💡 Liczy się rzadkość picku – mniej popularni = więcej punktów</span>
          <span>ESC zamknij</span>
        </div>
      </div>
    </div>
  )
}
