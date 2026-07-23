'use client'
import { DailySlot } from '@/lib/api'
import { roleNamesPl } from '@/lib/flags'
import { Pick } from '@/lib/store'
import { useState } from 'react'

type Props = {
  slots: DailySlot[]
  picks: Record<number, Pick | undefined>
  onPick: (slot: DailySlot) => void
  onClear: (slotId: number) => void
  disabled?: boolean
}

// Role icon component – loads SVG from /public/roles/ and tints it to warm
// cream via CSS filter (no colored chrome, no glow).
function RoleIcon({ role, state = 'empty', size = 44, diamond = false }: { role: string, state?: 'empty' | 'correct' | 'wrong', size?: number, diamond?: boolean }) {
  const src = `/roles/${role}.svg`
  const styles: Record<string, { border: string, icon: string }> = {
    empty:   { border: 'var(--line-strong)', icon: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)' },
    correct: { border: 'var(--warn)',        icon: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)' },
    wrong:   { border: 'var(--red)',         icon: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)' },
  }
  const s = styles[state] || styles.empty

  return (
    <div
      className="relative flex items-center justify-center rounded-full bg-elevated"
      style={{
        width: size,
        height: size,
        border: `2px solid ${s.border}`,
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={role}
        width={size * 0.62}
        height={size * 0.62}
        style={{ filter: s.icon, opacity: state === 'empty' ? 0.8 : 1 }}
        draggable={false}
      />
      {diamond && (
        <div className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full bg-accent border border-accent-ink" title="Diamond pick" />
      )}
      {state === 'correct' && (
        <div className="absolute -bottom-1 text-[10px] bg-accent text-accent-ink px-1.5 rounded-full font-bold leading-tight">✓</div>
      )}
      {state === 'wrong' && (
        <div className="absolute -bottom-1 text-[10px] bg-red text-bg px-1.5 rounded-full font-bold leading-tight">✗</div>
      )}
    </div>
  )
}

export default function RiftBoard({ slots, picks, onPick, onClear, disabled }: Props) {
  const [hoverRole, setHoverRole] = useState<string | null>(null)

  const byRole: Record<string, DailySlot | undefined> = {}
  slots.forEach(s => { byRole[s.role] = s })

  const positions = [
    { role: 'top',     left: '14%', top: '18%', label: 'TOP' },
    { role: 'jungle',  left: '30%', top: '42%', label: 'JUNGLE' },
    { role: 'mid',     left: '52%', top: '50%', label: 'MID' },
    { role: 'adc',     left: '72%', top: '72%', label: 'ADC' },
    { role: 'support', left: '82%', top: '84%', label: 'SUP' },
  ] as const

  return (
    <div className="relative w-full rounded-console border border-line-strong overflow-hidden bg-bg">
      <div className="relative w-full" style={{ aspectRatio: '1 / 1', maxHeight: '680px' }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/rift-map.png"
          alt="Summoner's Rift"
          className="absolute inset-0 w-full h-full object-cover"
          style={{ filter: 'brightness(0.7) contrast(1.02) saturate(0.75)', opacity: 0.9 }}
          draggable={false}
        />
        {/* quiet dark vignette (no colored glow) */}
        <div
          className="absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 38%, rgba(8,7,5,0.45) 78%, rgba(8,7,5,0.7) 100%)' }}
        />

        {positions.map(pos => {
          const slot = byRole[pos.role]
          if (!slot) return null
          const pick = picks[slot.id]
          const isHover = hoverRole === pos.role
          const nodeState = !pick ? 'empty' : pick.is_correct ? 'correct' : 'wrong'
          return (
            <div
              key={pos.role}
              className="absolute"
              style={{ left: pos.left, top: pos.top, transform: 'translate(-50%, -50%)' }}
              onMouseEnter={() => setHoverRole(pos.role)}
              onMouseLeave={() => setHoverRole(null)}
            >
              <button
                onClick={() => !disabled && onPick(slot)}
                disabled={!!(pick?.is_correct && pick?.locked) || disabled}
                className={`group relative flex flex-col items-center transition-transform duration-150 ${pick?.locked ? 'cursor-not-allowed' : 'hover:scale-105'} focus:outline-none`}
              >
                <RoleIcon role={pos.role} state={nodeState as any} size={68} diamond={!!pick?.is_diamond_pick} />
                <div className="mt-1.5 text-center">
                  <div className="text-[10px] tracking-widest text-accent font-semibold" style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                    {pos.label}
                  </div>
                  <div className="text-[11px] text-ink font-medium max-w-[120px] truncate" style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                    {pick?.playerNickname || <span className="text-muted">— wybierz —</span>}
                  </div>
                  {pick?.is_correct && (
                    <div className="text-[10px] font-semibold text-warn" style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                      ✓ {pick.pick_percent.toFixed(1)}% → -{pick.deduction}{pick.is_diamond_pick ? ' ◆' : ''}
                    </div>
                  )}
                  {pick && !pick.is_correct && (
                    <div className="text-[10px] font-semibold text-red" style={{ textShadow: '0 1px 3px rgba(0,0,0,0.6)' }}>
                      ✗ spróbuj ponownie
                    </div>
                  )}
                </div>

                {/* tooltip with conditions on hover */}
                <div className={`absolute left-1/2 -translate-x-1/2 ${pos.top?.includes('7') || pos.top?.includes('8') ? 'bottom-[100%] mb-2' : 'top-[100%] mt-2'}
                  ${isHover ? 'opacity-100' : 'opacity-0 pointer-events-none'}
                  transition-opacity duration-150 z-30 w-64`}>
                  <div className="bg-surface border border-line-strong rounded-console px-3 py-2 text-left">
                    <div className="text-[11px] text-accent font-semibold mb-1">
                      {roleNamesPl[pos.role as keyof typeof roleNamesPl]} – warunki:
                    </div>
                    <ul className="space-y-0.5">
                      {slot.conditions.map(c => (
                        <li key={c.id} className="text-[11px] text-ink/90">• {c.label_pl}</li>
                      ))}
                    </ul>
                    {pick && (
                      <div className="mt-1.5 pt-1.5 border-t border-line text-[10px] text-warn">
                        Wybrany: {pick.playerNickname}
                      </div>
                    )}
                  </div>
                </div>
              </button>

              {pick && !disabled && !(pick.is_correct && pick.locked) && (
                <button
                  onClick={(e) => { e.stopPropagation(); onClear(slot.id) }}
                  className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-bg border border-line-strong text-muted text-[11px] flex items-center justify-center hover:border-red hover:text-red transition-colors"
                  title="Usuń wybór"
                >×</button>
              )}
              {pick?.is_correct && pick?.locked && (
                <div className="absolute -top-1 -right-2 text-[9px] bg-surface border border-line-strong text-warn px-1 rounded">✓ LOCK</div>
              )}
              {pick && !pick.is_correct && (
                <div className="absolute -top-1 -right-2 text-[9px] bg-surface border border-line-strong text-red px-1 rounded">RETRY</div>
              )}
            </div>
          )
        })}

        {/* title strip */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full bg-bg/70 border border-line text-center">
          <div className="text-[10px] tracking-[0.2em] text-accent">WORLDS XI</div>
          <div className="text-[11px] text-muted">Kliknij ikonę roli → wybierz zawodnika</div>
        </div>
      </div>

      {/* bottom conditions strip – desktop */}
      <div className="hidden md:block bg-panel border-t border-line px-4 py-3">
        <div className="grid grid-cols-5 gap-3 text-[11px]">
          {(['top', 'jungle', 'mid', 'adc', 'support'] as const).map(r => {
            const slot = byRole[r]
            const pick = slot ? picks[slot.id] : undefined
            if (!slot) return <div key={r} />
            return (
              <div key={r} className="min-w-0">
                <div className="text-accent uppercase tracking-wider text-[10px] mb-0.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/roles/${r}.svg`} alt="" className="inline w-3 h-3 mr-1 align-[-2px]" style={{ filter: 'brightness(0) invert(0.82) sepia(0.16) saturate(0.55)' }} />
                  {r}
                </div>
                <div className="text-ink truncate font-medium">
                  {pick?.playerNickname || <span className="text-muted">—</span>}
                </div>
                <div className="text-muted truncate">
                  {slot.conditions.map(c => c.label_pl).join(' • ')}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
