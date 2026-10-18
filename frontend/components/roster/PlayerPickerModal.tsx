'use client'
import { useEffect, useId, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'
import { DailySlot, Player, usePlayerAutocomplete } from '@/lib/api'
import { roleLabel } from '@/lib/flags'
import { usePrefs } from '@/lib/store'
import { sound } from '@/lib/sound'
import { useDialog } from '../ui/useDialog'
import PlayerPortrait from './PlayerPortrait'

type Props = {
  slot: DailySlot | null
  open: boolean
  busy?: boolean
  error?: string | null
  onClose: () => void
  onSelect: (player: Player) => void
}

export default function PlayerPickerModal({ slot, open, busy, error, onClose, onSelect }: Props) {
  const locale = usePrefs((s) => s.locale)
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [highlight, setHighlight] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const dialogRef = useDialog<HTMLDivElement>(open, onClose)
  const titleId = useId()
  const listId = useId()

  const waitingForQuery = q.trim() !== search
  const query = usePlayerAutocomplete(open && !waitingForQuery ? search : '', slot?.role)
  const { data, isError, refetch } = query
  const isFetching = query.isFetching || waitingForQuery
  const results: Player[] = q.trim() ? data || [] : []

  useEffect(() => {
    if (!open || !q.trim()) { setSearch(''); return }
    const timer = setTimeout(() => setSearch(q.trim()), 250)
    return () => clearTimeout(timer)
  }, [q, open, slot?.id])

  useEffect(() => {
    if (open) {
      setQ('')
      setHighlight(0)
    }
  }, [open, slot?.id])

  useEffect(() => setHighlight(0), [q, data])
  useEffect(() => {
    if (open && !busy) inputRef.current?.focus()
  }, [open, busy, slot?.id])

  const onSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (busy || isFetching || isError || e.nativeEvent.isComposing) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setHighlight((h) => Math.min(h + 1, Math.max(0, results.length - 1)))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setHighlight((h) => Math.max(0, h - 1))
      }
      if (e.key === 'Enter' && results[highlight]) {
        e.preventDefault()
        sound.pick()
        onSelect(results[highlight])
      }
  }

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView?.({ block: 'nearest' })
  }, [highlight])

  if (!open || !slot) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-2 sm:p-6">
      <div className="picker-backdrop absolute inset-0" onClick={onClose} />

      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="panel picker-panel relative flex flex-col w-full max-w-lg max-h-[calc(100dvh-16px)] sm:max-h-[calc(100dvh-48px)] rise">
        {/* nagłówek: rola + warunki */}
        <div className="px-5 pt-5 pb-4 sm:px-6 sm:pt-6 border-b" style={{ borderColor: 'var(--line)' }}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="eyebrow" style={{ color: 'var(--gold-dim)' }}>
                {roleLabel(slot.role, locale)}
              </div>
              <h2 id={titleId} className="display text-[24px] mt-1">
                {locale === 'pl' ? 'Kto pasuje?' : 'Who fits?'}
              </h2>
            </div>
            <button onClick={onClose} className="p-2 -mr-2 -mt-2 hover:bg-[var(--panel-2)]" style={{ color: 'var(--text-faint)' }} aria-label={locale === 'pl' ? 'Zamknij' : 'Close'}>
              <X size={20} aria-hidden />
            </button>
          </div>
          <ul className="mt-4 space-y-2">
            {slot.conditions.map((c) => (
              <li
                key={c.id}
                className="text-[14px] leading-relaxed pl-3 border-l-2"
                style={{ borderColor: 'var(--gold-dim)', color: 'var(--text)' }}
              >
                {locale === 'pl' ? c.label_pl : c.label_en}
              </li>
            ))}
          </ul>
        </div>

        {/* wyszukiwarka */}
        <div className="px-5 py-4 sm:px-6 border-b" style={{ borderColor: 'var(--line)' }}>
          <div className="relative">
          <Search size={18} aria-hidden className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-faint)' }} />
          <input
            ref={inputRef}
            data-dialog-focus
            role="combobox"
            aria-label={locale === 'pl' ? 'Nick zawodnika' : 'Player nickname'}
            aria-autocomplete="list"
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-activedescendant={!isFetching && !isError && results[highlight] ? `${listId}-${results[highlight].id}` : undefined}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onSearchKey}
            autoComplete="off"
            placeholder={locale === 'pl' ? 'Wpisz nick zawodnika' : 'Type a player nickname'}
            className="field pl-11"
            disabled={busy}
          />
          </div>
          {error && (
            <div role="alert" className="mt-3 text-[13px] leading-relaxed shake" style={{ color: 'var(--bad)' }}>{error}</div>
          )}
        </div>

        {/* wyniki */}
        <div className="min-h-0 max-h-[42dvh] overflow-y-auto scroll-thin" aria-busy={isFetching || busy}>
          {q.trim().length === 0 && (
            <p className="p-6 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
              {locale === 'pl'
                ? 'Zawodnicy, którzy wystąpili na Worlds'
                : 'Players who appeared at Worlds'}
            </p>
          )}

          {q.trim().length > 0 && !isFetching && !isError && results.length === 0 && (
            <p className="p-6 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
              {locale === 'pl' ? 'Brak wyników' : 'No results'}
            </p>
          )}

          {isError && (
            <button className="w-full p-4 text-[13px]" onClick={() => refetch()} style={{ color: 'var(--bad)' }}>
              {locale === 'pl' ? 'Nie udało się wyszukać. Spróbuj ponownie.' : 'Search failed. Try again.'}
            </button>
          )}

          <ul ref={listRef} id={listId} role="listbox" aria-label={locale === 'pl' ? 'Zawodnicy' : 'Players'}>
            {!isFetching && !isError && results.map((p, i) => (
              <li key={p.slug} role="presentation">
                <button
                  id={`${listId}-${p.id}`}
                  role="option"
                  aria-selected={i === highlight}
                  tabIndex={-1}
                  data-active={i === highlight}
                  onMouseEnter={() => setHighlight(i)}
                  onClick={() => { if (!busy) { sound.pick(); onSelect(p) } }}
                  disabled={busy}
                  className="picker-option w-full text-left px-5 sm:px-6 py-3.5 flex items-center gap-3 border-l-2 border-transparent transition disabled:opacity-50"
                >
                  <PlayerPortrait url={p.portrait_url} />
                  <span className="min-w-0 truncate text-[15px] font-bold">{p.nickname}</span>
                </button>
              </li>
            ))}
          </ul>

          {(isFetching || busy) && (
            <p role="status" className="p-4 text-center text-[13px]" style={{ color: 'var(--text-faint)' }}>
              {busy ? (locale === 'pl' ? 'Sprawdzam…' : 'Checking…') : (locale === 'pl' ? 'Szukam…' : 'Searching…')}
            </p>
          )}
        </div>

        <div
          className="shrink-0 px-5 sm:px-6 py-3 border-t flex justify-between text-[11px]"
          style={{ borderColor: 'var(--line)', color: 'var(--text-faint)' }}
        >
          <span>↑ ↓ <span className="ml-2">Enter</span></span>
          <span>Esc</span>
        </div>
      </div>
    </div>
  )
}
