'use client'
import { useState, useEffect, useMemo } from 'react'
import { usePlayers, searchPlayers, Player, DailySlot } from '@/lib/api'
import { countryFlag, countryLabel } from '@/lib/flags'
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

  useEffect(() => { if (open) setQ('') }, [open, slot?.id])

  const list: Player[] = useMemo(() => {
    if (!players) return []
    if (q.length === 0) {
      const rolePlayers = players
        .filter(p => p.primary_role === slot?.role)
        .sort((a, b) => (b.worlds_count - a.worlds_count) || a.nickname.localeCompare(b.nickname))
      return rolePlayers.slice(0, 30)
    }
    return searchPlayers(players, q)
  }, [q, players, slot?.role])

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    if (open) window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open || !slot) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-full max-w-2xl mx-4 bg-panel border border-line-strong rounded-console overflow-hidden">
        {/* header */}
        <div className="px-5 py-4 border-b border-line bg-surface flex items-center justify-between">
          <div>
            <div className="text-xs text-accent uppercase tracking-wider">
              {slot.role.toUpperCase()}
            </div>
            <div className="text-lg font-semibold text-ink">Wybierz zawodnika</div>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {slot.conditions.map(c => (
                <span key={c.id} className="text-[11px] px-2 py-0.5 rounded-control bg-bg border border-line text-muted">{c.label_pl}</span>
              ))}
            </div>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink text-xl px-2 transition-colors">×</button>
        </div>

        {/* search */}
        <div className="p-4 border-b border-line">
          <input
            autoFocus
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Szukaj: Faker, Caps, Jankos…"
            className="field text-base"
          />
          <div className="text-[11px] text-muted mt-2">
            {q ? `Wyniki dla "${q}" — ${list.length}` : `Sugestie dla roli ${slot.role.toUpperCase()} – wpisz nick aby wyszukać w całej bazie.`}
          </div>
        </div>

        {/* list – tylko nick + kraj pochodzenia */}
        <div className="max-h-[55vh] overflow-y-auto">
          {currentPick && (
            <div className="px-4 py-2 text-xs text-accent border-b border-line bg-accent-soft">
              Aktualny wybór: <b>{currentPick.playerNickname}</b> – kliknij innego aby zmienić
            </div>
          )}
          {isLoading && <div className="p-4 text-center text-muted text-sm">Ładowanie bazy graczy…</div>}
          {!isLoading && list.length === 0 && q.length > 0 && (
            <div className="p-6 text-center text-muted">Brak wyników</div>
          )}
          <ul className="divide-y divide-line">
            {list.map(p => (
              <li key={p.slug}>
                <button
                  onClick={() => { sound.pick(); onSelect(p.slug, p.nickname) }}
                  className="w-full text-left px-4 py-3 hover:bg-surface flex items-center gap-3 transition-colors"
                >
                  <div className="text-2xl w-9 text-center leading-none">
                    {countryFlag(p.country_code)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-ink truncate">{p.nickname}</div>
                    <div className="text-xs text-muted truncate">{countryLabel(p.country_code)}</div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* footer */}
        <div className="px-4 py-3 border-t border-line bg-surface text-[11px] text-muted flex justify-between">
          <span>Rzadkość picku się liczy – mniej popularni = więcej punktów</span>
          <span>ESC zamknij</span>
        </div>
      </div>
    </div>
  )
}
