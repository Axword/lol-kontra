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

export default function RiftBoard({ slots, picks, onPick, onClear, disabled }: Props) {
  const roles = ['top', 'jungle', 'mid', 'adc', 'support'] as const
  const byRole: Record<string, DailySlot | undefined> = {}
  slots.forEach(s => { byRole[s.role] = s })

  return (
    <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 sm:gap-3">
      {roles.map(role => {
        const slot = byRole[role]
        if (!slot) return null
        const pick = picks[slot.id]
        const nodeState = !pick ? 'empty' : pick.is_correct ? 'correct' : 'wrong'
        const isLocked = pick?.is_correct && pick?.locked

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
            {/* Header: role icon + label */}
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

            {/* Conditions – always visible */}
            <div className="px-3 py-2 border-t border-line">
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
                onClick={() => onClear(slot.id)}
                className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-bg border border-line text-muted text-[11px] flex items-center justify-center hover:border-red hover:text-red transition-colors"
                title="Usuń wybór"
              >×</button>
            )}
          </div>
        )
      })}
    </div>
  )
}
