'use client'
import { useState, useEffect, useMemo, useRef } from 'react'
import { usePlayers, searchPlayers, Player, DailySlot } from '@/lib/api'
import { countryCode, countryLabel, roleLabel } from '@/lib/flags'
import { Pick, usePrefs } from '@/lib/store'
import { sound } from '@/lib/sound'

export default function PlayerPickerModal({
  slot, open, currentPick, onSelect, onClose,
}: {
  slot: DailySlot | null
  open: boolean
  currentPick?: Pick
  onSelect: (slug: string, nickname: string) => void
  onClose: () => void
}) {
  const locale = usePrefs(s => s.locale)
  const [q, setQ] = useState('')
  const [highlight, setHighlight] = useState(0)
  const { data: players, isLoading } = usePlayers()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  useEffect(() => {
    if (!open) return
    setQ('')
    setHighlight(0)
    const t = setTimeout(() => inputRef.current?.focus(), 30)
    return () => clearTimeout(t)
  }, [open, slot?.id])

  useEffect(() => setHighlight(0), [q])

  /**
   * Lista jest ZAWSZE zawężona do roli slotu. Wcześniej wyszukiwanie
   * przeszukiwało całą bazę, więc dla slotu topa podpowiadało supportów –
   * każdy taki wybór był z definicji błędny i kosztował życie.
   */
  const list: Player[] = useMemo(() => {
    if (!players || !slot) return []
    if (!q.trim()) {
      return players
        .filter(p => p.primary_role === slot.role)
        .sort((a, b) => (b.worlds_count - a.worlds_count) || a.nickname.localeCompare(b.nickname))
        .slice(0, 40)
    }
    return searchPlayers(players, q, slot.role)
  }, [q, players, slot])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(h => Math.min(h + 1, list.length - 1)) }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(h => Math.max(0, h - 1)) }
      if (e.key === 'Enter' && list[highlight]) {
        e.preventDefault()
        sound.pick()
        onSelect(list[highlight].slug, list[highlight].nickname)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, list, highlight, onClose, onSelect])

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [highlight])

  if (!open || !slot) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-3">
      <div className="absolute inset-0 bg-black/75" onClick={onClose} />

      <div className="console relative w-full max-w-xl mt-10 sm:mt-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-line bg-surface">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="eyebrow text-accent">{roleLabel(slot.role, locale)}</div>
              <div className="text-[16px] font-semibold text-ink mt-0.5">
                {locale === 'pl' ? 'Kto pasuje?' : 'Who fits?'}
              </div>
            </div>
            <button onClick={onClose} className="text-muted hover:text-ink text-xl leading-none px-1 transition-colors" aria-label="Zamknij">×</button>
          </div>
          <ul className="mt-2 space-y-1">
            {slot.conditions.map(c => (
              <li key={c.id} className="text-[13px] text-ink pl-2.5 border-l border-accent">
                {locale === 'pl' ? c.label_pl : c.label_en}
              </li>
            ))}
          </ul>
        </div>

        <div className="p-3 border-b border-line">
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder={locale === 'pl' ? 'Wpisz nick zawodnika' : 'Type a player nickname'}
            className="field"
          />
          {currentPick && !currentPick.is_correct && (
            <div className="text-[12px] text-red mt-2">
              {locale === 'pl'
                ? `${currentPick.playerNickname} nie pasował – spróbuj kogoś innego.`
                : `${currentPick.playerNickname} did not fit – try someone else.`}
            </div>
          )}
        </div>

        <div className="max-h-[46vh] overflow-y-auto">
          {isLoading && (
            <p className="p-5 text-center text-muted text-[13px]">
              {locale === 'pl' ? 'Wczytuję bazę zawodników…' : 'Loading the player database…'}
            </p>
          )}
          {!isLoading && list.length === 0 && (
            <p className="p-6 text-center text-muted text-[13px]">
              {locale === 'pl' ? 'Brak wyników' : 'No results'}
            </p>
          )}
          <ul ref={listRef}>
            {list.map((p, i) => (
              <li key={p.slug}>
                <button
                  data-active={i === highlight}
                  onMouseEnter={() => setHighlight(i)}
                  onClick={() => { sound.pick(); onSelect(p.slug, p.nickname) }}
                  className="w-full text-left px-4 py-2.5 flex items-center gap-3 border-l-2 transition-colors"
                  style={{
                    borderColor: i === highlight ? 'var(--accent)' : 'transparent',
                    background: i === highlight ? 'var(--accent-soft)' : 'transparent',
                  }}
                >
                  <span className="cc">{countryCode(p.country_code)}</span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-[14px] text-ink truncate">{p.nickname}</span>
                    <span className="block text-[11px] text-muted truncate">
                      {countryLabel(p.country_code, locale)}
                      {p.real_name ? ` · ${p.real_name}` : ''}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="px-4 py-2.5 border-t border-line bg-surface text-[11px] text-muted flex justify-between">
          <span>{locale === 'pl' ? 'Strzałki i Enter działają' : 'Arrow keys and Enter work'}</span>
          <span>Esc</span>
        </div>
      </div>
    </div>
  )
}
