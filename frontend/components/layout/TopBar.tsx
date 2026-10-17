'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePrefs } from '@/lib/store'
import { sound, isSoundEnabled, toggleSound } from '@/lib/sound'

type Props = {
  dailyId?: number
  dailyDate?: string
  /** null = gra jeszcze nie skończona, nie ma czego pokazywać */
  score?: number | null
  correct?: number
  slotsTotal?: number
  errorsLeft?: number
  errorsTotal?: number
  onMenu: () => void
  onHelp: () => void
}

/** Znaczniki żyć – prostokątne kreski zamiast kropek. */
function Lives({ left, total }: { left: number; total: number }) {
  return (
    <span className="flex items-end gap-[3px]" aria-hidden>
      {Array.from({ length: total }).map((_, i) => {
        const spent = i >= left
        return (
          <span
            key={i}
            className="tick"
            style={{
              height: spent ? 7 : 12,
              background: spent ? 'var(--line-strong)' : 'var(--warn)',
            }}
          />
        )
      })}
    </span>
  )
}

function Tool({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="w-[30px] h-[28px] rounded-control border border-line text-muted hover:text-ink hover:border-muted flex items-center justify-center transition-colors"
    >
      {children}
    </button>
  )
}

/**
 * Jeden pasek zamiast dwóch.
 *
 * Poprzednia wersja miała górny pasek (język, linki) i dolny (błędy, dźwięk),
 * a pomiędzy nimi trzeci rząd wstrzykiwany przez GameLayout z wynikiem i
 * trafieniami. Trzy rzędy chrome'u nad planszą to była większość pierwszego
 * ekranu na telefonie.
 */
export default function TopBar({
  dailyId, dailyDate, score, correct = 0, slotsTotal = 5,
  errorsLeft = 10, errorsTotal = 10, onMenu, onHelp,
}: Props) {
  const locale = usePrefs(s => s.locale)
  const setLocale = usePrefs(s => s.setLocale)
  const [snd, setSnd] = useState(true)

  // Odczyt z localStorage dopiero po zamontowaniu – inaczej serwer renderuje
  // inną ikonę niż klient i React zgłasza błąd hydracji.
  useEffect(() => setSnd(isSoundEnabled()), [])

  const dateLabel = dailyDate
    ? new Date(dailyDate + 'T12:00:00').toLocaleDateString(locale === 'pl' ? 'pl-PL' : 'en-GB', {
        day: 'numeric', month: 'long',
      })
    : ''

  return (
    <header className="sticky top-0 z-30 bg-panel border-b border-line">
      <div className="max-w-[1180px] mx-auto px-3 sm:px-5 h-[56px] flex items-center gap-3 sm:gap-5">
        <button
          onClick={onMenu}
          className="lg:hidden -ml-1 p-2 text-muted hover:text-ink transition-colors"
          aria-label="Menu"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M1 4h16M1 9h16M1 14h16" />
          </svg>
        </button>

        <Link href="/" className="min-w-0 hidden sm:block">
          <div className="text-[15px] font-semibold text-ink leading-none">Worlds XI</div>
          <div className="eyebrow mt-[3px] truncate">
            {dailyId ? `#${dailyId}` : ''}{dateLabel ? ` · ${dateLabel}` : ''}
          </div>
        </Link>

        {/* liczniki gry */}
        <div className="ml-auto flex items-center gap-4 sm:gap-6">
          <div className="text-right">
            <div className="eyebrow">{locale === 'pl' ? 'Wynik' : 'Score'}</div>
            <div className="mono text-[17px] leading-tight text-ink">
              {score == null ? '—' : score}
            </div>
          </div>

          <div className="text-right hidden xs:block sm:block">
            <div className="eyebrow">{locale === 'pl' ? 'Trafione' : 'Correct'}</div>
            <div className="mono text-[17px] leading-tight text-ink">
              {correct}<span className="text-muted">/{slotsTotal}</span>
            </div>
          </div>

          <div className="text-right">
            <div className="eyebrow">{locale === 'pl' ? 'Życia' : 'Lives'}</div>
            <div className="flex items-center gap-2 justify-end mt-[3px]">
              <Lives left={errorsLeft} total={errorsTotal} />
              <span className="mono text-[13px] text-muted">{errorsLeft}</span>
            </div>
          </div>
        </div>

        {/* narzędzia */}
        <div className="flex items-center gap-1.5 pl-2 sm:pl-4 border-l border-line">
          <div className="flex rounded-control border border-line overflow-hidden">
            {(['pl', 'en'] as const).map(l => (
              <button
                key={l}
                onClick={() => { setLocale(l); sound.click() }}
                className={`px-2 py-[5px] text-[10px] uppercase tracking-[0.12em] transition-colors ${
                  locale === l ? 'bg-accent text-accent-ink' : 'text-muted hover:text-ink'
                }`}
              >{l}</button>
            ))}
          </div>

          <Tool
            label={snd ? 'Wyłącz dźwięk' : 'Włącz dźwięk'}
            onClick={() => { const n = toggleSound(); setSnd(n); if (n) sound.click() }}
          >
            {snd ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
                <path d="M2 6h3l4-3v10L5 10H2z" /><path d="M11.5 5.5a3.5 3.5 0 0 1 0 5" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
                <path d="M2 6h3l4-3v10L5 10H2z" /><path d="M11 6l4 4M15 6l-4 4" />
              </svg>
            )}
          </Tool>

          <Tool label={locale === 'pl' ? 'Zasady gry' : 'How to play'} onClick={() => { sound.open(); onHelp() }}>
            <span className="text-[12px] leading-none">?</span>
          </Tool>
        </div>
      </div>
    </header>
  )
}
