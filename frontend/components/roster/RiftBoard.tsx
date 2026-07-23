'use client'
import { DailySlot } from '@/lib/api'
import { Pick } from '@/lib/store'

type Props = {
  slots: DailySlot[]
  picks: Record<number, Pick | undefined>
  onPick: (slot: DailySlot) => void
  onClear: (slotId: number) => void
  disabled?: boolean
}

function RoleIcon({ role, state = 'empty', size = 48 }: { role: string, state?: 'empty' | 'correct' | 'wrong', size?: number }) {
  const src = `/roles/${role}.svg`
  const borderColor = state === 'correct' ? 'var(--warn)' : state === 'wrong' ? 'var(--red)' : 'var(--line-strong)'
  return (
    <div
      className="flex items-center justify-center rounded-full bg-elevated shrink-0"
      style={{ width: size, height: size, border: `2px solid ${borderColor}` }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={role}
        width={size * 0.6}
        height={size * 0.6}
        style={{ filter: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)', opacity: state === 'empty' ? 0.7 : 1 }}
        draggable={false}
      />
    </div>
  )
}

/**
 * Map positions for each role on the Summoner's Rift layout.
 * Values are in percentages of the map container.
 * Positions carefully spaced to avoid overlapping on 768px+ screens.
 */
const MAP_POSITIONS: Record<string, { top: string; left: string; anchor: string }> = {
  top:     { top: '2%',   left: '2%',   anchor: 'start' },   // top-left (toplane)
  jungle:  { top: '36%',  left: '2%',   anchor: 'start' },   // center-left (jungle)
  mid:     { top: '2%',   left: '40%',  anchor: 'center' },  // top-center (midlane)
  adc:     { top: '36%',  left: '78%',  anchor: 'end' },     // center-right (botlane)
  support: { top: '68%',  left: '40%',  anchor: 'center' },  // bottom-center (support)
}

function RoleCard({
  slot,
  pick,
  nodeState,
  isLocked,
  disabled,
  onPick,
  onClear,
  pos,
}: {
  slot: DailySlot
  pick: Pick | undefined
  nodeState: 'empty' | 'correct' | 'wrong'
  isLocked: boolean
  disabled: boolean
  onPick: () => void
  onClear: () => void
  pos: { top: string; left: string; anchor: string }
}) {
  // Determine card alignment based on map position
  const translateX = pos.anchor === 'end' ? '-100%' : pos.anchor === 'center' ? '-50%' : '0%'

  return (
    <div
      className="absolute z-10 w-[180px] lg:w-[200px]"
      style={{
        top: pos.top,
        left: pos.left,
        transform: `translateX(${translateX})`,
      }}
    >
      <div
        className={`relative rounded-console border backdrop-blur-sm transition-colors ${
          nodeState === 'correct'
            ? 'border-warn/40 bg-accent-soft/60'
            : nodeState === 'wrong'
              ? 'border-red/30 bg-red/10'
              : 'border-line-strong bg-panel/90 hover:border-muted'
        }`}
      >
        {/* Header: role icon + label */}
        <button
          onClick={() => !disabled && !isLocked && onPick()}
          disabled={!!isLocked || disabled}
          className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors ${
            isLocked ? 'cursor-default' : 'hover:bg-surface/60 cursor-pointer'
          }`}
        >
          <RoleIcon role={slot.role} state={nodeState} size={36} />
          <div className="min-w-0 flex-1">
            <div className="text-[10px] uppercase tracking-widest text-accent font-semibold">
              {slot.role}
            </div>
            <div className="text-[13px] font-semibold text-ink truncate">
              {pick?.playerNickname || <span className="text-muted font-normal">wybierz…</span>}
            </div>
          </div>
          {/* Status badge */}
          {pick?.is_diamond_pick && (
            <div className="text-[10px] bg-accent text-accent-ink px-1.5 py-0.5 rounded font-bold shrink-0">◆</div>
          )}
          {nodeState === 'correct' && !pick?.is_diamond_pick && (
            <div className="text-[11px] text-warn font-bold shrink-0">✓</div>
          )}
          {nodeState === 'wrong' && (
            <div className="text-[11px] text-red font-bold shrink-0">✗</div>
          )}
        </button>

        {/* Pick result */}
        {pick?.is_correct && (
          <div className="px-3 pb-1.5">
            <div className="text-[11px] font-semibold text-warn">
              {pick.pick_percent.toFixed(1)}% → -{pick.deduction}{pick.is_diamond_pick ? ' ◆' : ''}
            </div>
          </div>
        )}
        {pick && !pick.is_correct && (
          <div className="px-3 pb-1.5">
            <div className="text-[11px] text-red">✗ spróbuj ponownie</div>
          </div>
        )}

        {/* Conditions – always visible */}
        <div className="px-3 py-1.5 border-t border-line">
          <ul className="space-y-0.5">
            {slot.conditions.map(c => (
              <li key={c.id} className="text-[11px] text-ink/80 leading-snug">
                <span className="text-accent/70 mr-1">›</span>{c.label_pl}
              </li>
            ))}
          </ul>
        </div>

        {/* Clear button */}
        {pick && !disabled && !isLocked && (
          <button
            onClick={onClear}
            className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-bg border border-line text-muted text-[11px] flex items-center justify-center hover:border-red hover:text-red transition-colors"
            title="Usuń wybór"
          >×</button>
        )}
      </div>
    </div>
  )
}

export default function RiftBoard({ slots, picks, onPick, onClear, disabled }: Props) {
  const roles = ['top', 'jungle', 'mid', 'adc', 'support'] as const
  const byRole: Record<string, DailySlot | undefined> = {}
  slots.forEach(s => { byRole[s.role] = s })

  return (
    <>
      {/* Desktop: Map layout */}
      <div className="hidden md:block relative w-full" style={{ aspectRatio: '16/11' }}>
        {/* Map background */}
        <div
          className="absolute inset-0 rounded-console overflow-visible"
          style={{
            backgroundImage: 'url(/rift-map.png)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            opacity: 0.55,
          }}
        />
        {/* Dark overlay for contrast */}
        <div className="absolute inset-0 rounded-console bg-bg/30" />

        {/* Role cards positioned on the map */}
        {roles.map(role => {
          const slot = byRole[role]
          if (!slot) return null
          const pick = picks[slot.id]
          const nodeState = !pick ? 'empty' : pick.is_correct ? 'correct' : 'wrong'
          const isLocked = !!(pick?.is_correct && pick?.locked)
          const pos = MAP_POSITIONS[role]

          return (
            <RoleCard
              key={role}
              slot={slot}
              pick={pick}
              nodeState={nodeState}
              isLocked={isLocked}
              disabled={!!disabled}
              onPick={() => onPick(slot)}
              onClear={() => onClear(slot.id)}
              pos={pos}
            />
          )
        })}
      </div>

      {/* Mobile: Vertical stack (no map) */}
      <div className="md:hidden grid grid-cols-1 gap-2">
        {roles.map(role => {
          const slot = byRole[role]
          if (!slot) return null
          const pick = picks[slot.id]
          const nodeState = !pick ? 'empty' : pick.is_correct ? 'correct' : 'wrong'
          const isLocked = !!(pick?.is_correct && pick?.locked)

          return (
            <div
              key={role}
              className={`relative rounded-console border transition-colors ${
                nodeState === 'correct'
                  ? 'border-warn/40 bg-accent-soft/50'
                  : nodeState === 'wrong'
                    ? 'border-red/30 bg-red/5'
                    : 'border-line-strong bg-panel hover:border-muted'
              }`}
            >
              <button
                onClick={() => !disabled && !isLocked && onPick(slot)}
                disabled={!!isLocked || disabled}
                className={`w-full flex items-center gap-2.5 px-3 py-3 text-left transition-colors ${
                  isLocked ? 'cursor-default' : 'hover:bg-surface/60 cursor-pointer'
                }`}
              >
                <RoleIcon role={role} state={nodeState} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] uppercase tracking-widest text-accent font-semibold">
                    {role}
                  </div>
                  <div className="text-[13px] font-semibold text-ink truncate">
                    {pick?.playerNickname || <span className="text-muted font-normal">wybierz…</span>}
                  </div>
                </div>
                {pick?.is_diamond_pick && (
                  <div className="text-[10px] bg-accent text-accent-ink px-1.5 py-0.5 rounded font-bold shrink-0">◆</div>
                )}
                {nodeState === 'correct' && !pick?.is_diamond_pick && (
                  <div className="text-[11px] text-warn font-bold shrink-0">✓</div>
                )}
                {nodeState === 'wrong' && (
                  <div className="text-[11px] text-red font-bold shrink-0">✗</div>
                )}
              </button>

              {pick?.is_correct && (
                <div className="px-3 pb-2">
                  <div className="text-[11px] font-semibold text-warn">
                    {pick.pick_percent.toFixed(1)}% → -{pick.deduction}{pick.is_diamond_pick ? ' ◆' : ''}
                  </div>
                </div>
              )}
              {pick && !pick.is_correct && (
                <div className="px-3 pb-2">
                  <div className="text-[11px] text-red">✗ spróbuj ponownie</div>
                </div>
              )}

              <div className="px-3 py-2 border-t border-line">
                <ul className="space-y-0.5">
                  {slot.conditions.map(c => (
                    <li key={c.id} className="text-[11px] text-ink/80 leading-snug">
                      <span className="text-accent/70 mr-1">›</span>{c.label_pl}
                    </li>
                  ))}
                </ul>
              </div>

              {pick && !disabled && !isLocked && (
                <button
                  onClick={() => onClear(slot.id)}
                  className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-bg border border-line text-muted text-[11px] flex items-center justify-center hover:border-red hover:text-red transition-colors"
                  title="Usuń wybór"
                >×</button>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
