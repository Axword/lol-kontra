'use client'
import { DailySlot } from '@/lib/api'
import { rarityClass, rarityLabel, roleLabel } from '@/lib/flags'
import { Pick, usePrefs } from '@/lib/store'

type Props = {
  slots: DailySlot[]
  picks: Record<number, Pick | undefined>
  onPick: (slot: DailySlot) => void
  onClear: (slotId: number) => void
  disabled?: boolean
  activeSlotId?: number | null
}

/**
 * Pozycje węzłów na mapie. `z` porządkuje nakładanie się podpisów – węzły
 * bliżej góry mapy przykrywają te niżej, dzięki czemu etykiety sąsiednich
 * pozycji nie mieszają się na wąskich ekranach.
 */
const POSITIONS: Record<string, { left: string; top: string; z: number }> = {
  top:     { left: '16%', top: '18%', z: 5 },
  jungle:  { left: '32%', top: '44%', z: 4 },
  mid:     { left: '50%', top: '52%', z: 3 },
  adc:     { left: '68%', top: '70%', z: 2 },
  support: { left: '85%', top: '85%', z: 1 },
}

type NodeState = 'empty' | 'wrong' | 'active' | 'correct'

function nodeColors(state: NodeState, diamond: boolean, tier?: string | null) {
  if (state === 'empty') return { edge: 'var(--line-strong)', fill: 'rgba(28,24,19,.9)', dim: true }
  if (state === 'wrong') return { edge: 'var(--red)', fill: 'rgba(48,26,24,.92)', dim: false }
  if (state === 'active') return { edge: 'var(--accent)', fill: 'rgba(52,32,20,.92)', dim: false }
  if (diamond) return { edge: 'var(--ink)', fill: 'rgba(36,32,26,.92)', dim: false }
  const edge = tier === 'legendary' ? 'var(--warn)' : tier === 'epic' ? 'var(--accent)' : 'var(--blue)'
  return { edge, fill: 'rgba(30,27,21,.92)', dim: false }
}

function RoleNode({ role, state, diamond, tier }: {
  role: string; state: NodeState; diamond: boolean; tier?: string | null
}) {
  const c = nodeColors(state, diamond, tier)
  return (
    <span className="node">
      <span className="node-shape" style={{ background: c.edge, transition: 'background 150ms' }} />
      <span className="node-shape" style={{ inset: 2, background: c.fill, transition: 'background 150ms' }} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/roles/${role}.svg`}
        alt=""
        aria-hidden
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 select-none"
        style={{
          width: 'calc(var(--node) * .42)',
          height: 'calc(var(--node) * .42)',
          filter: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)',
          opacity: c.dim ? 0.55 : 1,
        }}
        draggable={false}
      />
    </span>
  )
}

export default function RiftBoard({ slots, picks, onPick, onClear, disabled, activeSlotId }: Props) {
  const locale = usePrefs(s => s.locale)
  const byRole: Record<string, DailySlot | undefined> = {}
  slots.forEach(s => { byRole[s.role] = s })

  return (
    <div className="space-y-3">
      {/* Mapa ma stały stosunek 1:1, więc na szerokim ekranie ograniczamy ją –
          rozciągnięta na całą szerokość byłaby wyższa niż ekran. */}
      <div
        className="console relative w-full mx-auto overflow-hidden"
        style={{
          aspectRatio: '1 / 1',
          maxWidth: 620,
          // Jedna zmienna steruje wielkością węzłów i podpisów.
          ['--node' as any]: 'clamp(38px, 11vw, 60px)',
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/rift-map.png"
          alt=""
          aria-hidden
          className="absolute inset-0 w-full h-full object-cover"
          style={{ filter: 'brightness(0.5) contrast(1.02) saturate(0.55)', opacity: 0.85 }}
          draggable={false}
        />
        <div
          className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 34%, rgba(8,7,5,0.5) 76%, rgba(8,7,5,0.78) 100%)' }}
        />

        {Object.entries(POSITIONS).map(([role, pos]) => {
          const slot = byRole[role]
          if (!slot) return null
          const pick = picks[slot.id]
          const correct = pick?.is_correct === true
          const state: NodeState = correct ? 'correct'
            : pick ? 'wrong'
            : activeSlotId === slot.id ? 'active'
            : 'empty'
          const tone = correct
            ? (pick!.is_diamond_pick ? 'text-ink' : rarityClass[pick!.rarity_tier || 'common'])
            : pick ? 'text-red' : 'text-muted'

          return (
            <div
              key={role}
              className="absolute"
              style={{
                left: pos.left, top: pos.top,
                transform: 'translate(-50%, -50%)',
                zIndex: activeSlotId === slot.id ? 20 : pos.z,
              }}
            >
              <button
                onClick={() => !disabled && !correct && onPick(slot)}
                disabled={disabled || correct}
                className="flex flex-col items-center gap-1.5 focus:outline-none"
                style={{ cursor: disabled || correct ? 'default' : 'pointer' }}
                aria-label={`${roleLabel(role, locale)} – ${pick?.playerNickname || (locale === 'pl' ? 'puste' : 'empty')}`}
              >
                <RoleNode
                  role={role}
                  state={state}
                  diamond={!!pick?.is_diamond_pick}
                  tier={pick?.rarity_tier}
                />
                <span
                  className="px-1.5 py-[2px] text-center bg-bg/85 border border-line rounded-control"
                  style={{ minWidth: 'calc(var(--node) * 1.3)', maxWidth: 'calc(var(--node) * 2.2)' }}
                >
                  <span className="block eyebrow" style={{ fontSize: 'clamp(8px, 2vw, 10px)' }}>
                    {roleLabel(role, locale)}
                  </span>
                  <span
                    className={`block leading-tight truncate ${tone}`}
                    style={{ fontSize: 'clamp(10px, 2.4vw, 12px)' }}
                  >
                    {pick?.playerNickname || (locale === 'pl' ? 'wybierz' : 'pick')}
                  </span>
                  {correct && (
                    <span className={`block mono ${tone}`} style={{ fontSize: 'clamp(8px, 2vw, 10px)' }}>
                      {pick!.pick_percent.toFixed(1)}% · −{pick!.deduction}
                    </span>
                  )}
                </span>
              </button>

              {/* Nietrafiony wybór można wyczyścić; trafiony jest zablokowany. */}
              {pick && !correct && !disabled && (
                <button
                  onClick={(e) => { e.stopPropagation(); onClear(slot.id) }}
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-control bg-bg border border-line-strong text-muted text-[11px] leading-none flex items-center justify-center hover:border-red hover:text-red transition-colors"
                  title={locale === 'pl' ? 'Wyczyść' : 'Clear'}
                >×</button>
              )}
            </div>
          )
        })}
      </div>

      {/*
        Warunki slotów – jedno miejsce, w którym są widoczne bez otwierania
        panelu. Wcześniej ten pasek był ukryty poniżej breakpointu md, a na
        telefonie warunki dało się zobaczyć wyłącznie przez dymek po najechaniu
        myszą, czyli w praktyce wcale.
      */}
      <div className="console px-3 py-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {Object.keys(POSITIONS).map(role => {
            const slot = byRole[role]
            if (!slot) return <div key={role} />
            const pick = picks[slot.id]
            const correct = pick?.is_correct === true
            return (
              <button
                key={role}
                onClick={() => !disabled && !correct && onPick(slot)}
                disabled={disabled || correct}
                className="text-left rounded-control border border-line p-2.5 hover:border-muted transition-colors disabled:hover:border-line"
                style={{ cursor: disabled || correct ? 'default' : 'pointer' }}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="eyebrow text-accent">{roleLabel(role, locale)}</span>
                  {correct && (
                    <span className={`text-[10px] uppercase tracking-[0.1em] ${pick!.is_diamond_pick ? 'r-diamond' : rarityClass[pick!.rarity_tier || 'common']}`}>
                      {pick!.is_diamond_pick
                        ? (locale === 'pl' ? 'Najrzadszy' : 'Rarest')
                        : rarityLabel(pick!.rarity_tier, locale)}
                    </span>
                  )}
                </div>
                <ul className="mt-1.5 space-y-0.5">
                  {slot.conditions.map(c => (
                    <li key={c.id} className="text-[12px] leading-snug text-ink/85 pl-2 border-l border-line">
                      {locale === 'pl' ? c.label_pl : c.label_en}
                    </li>
                  ))}
                </ul>
                <div className="mt-2 pt-2 border-t border-line text-[12px]">
                  {correct ? (
                    <span className="text-ink">{pick!.playerNickname}</span>
                  ) : pick ? (
                    <span className="text-red">
                      {pick.playerNickname} — {locale === 'pl' ? 'nie pasuje' : 'no match'}
                    </span>
                  ) : (
                    <span className="text-muted">{locale === 'pl' ? 'Kliknij, aby zgadywać' : 'Tap to guess'}</span>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
