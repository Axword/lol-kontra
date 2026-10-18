'use client'
import { Check, ChevronRight } from 'lucide-react'
import { DailySlot, GameAnswer } from '@/lib/api'
import { roleLabel } from '@/lib/flags'
import { usePrefs } from '@/lib/store'
import { formatDeduction } from '@/lib/points'

type Props = { slots: DailySlot[]; answers: Record<number, GameAnswer>; onPick: (slot: DailySlot) => void; disabled?: boolean; inspect?: boolean; candidateCounts?: Record<number, number> }

export default function SlotList({ slots, answers, onPick, disabled, inspect = false, candidateCounts }: Props) {
  const locale = usePrefs((s) => s.locale)
  return (
    <div className="slot-list-mobile border divide-y" style={{ borderColor: 'var(--line)' }}>
      {slots.map((slot) => {
        const answer = answers[slot.id]
        const solved = answer?.is_correct === true
        const count = candidateCounts?.[slot.id]
        return (
          <button key={slot.id} onClick={() => !disabled && (!solved || inspect) && onPick(slot)} disabled={disabled || (solved && !inspect)} className="flex items-center gap-3 p-4 text-left bg-white" style={{ borderColor: 'var(--line)', opacity: disabled && !solved ? .6 : 1 }}>
            <span className="w-9 h-9 flex items-center justify-center shrink-0 border" style={{ borderColor: 'var(--line)', background: 'var(--panel-2)' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/roles/${slot.role}.svg`} alt="" aria-hidden className="w-6 h-6" style={{ filter: 'brightness(.3)' }} />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-[13px] font-bold mb-1">{roleLabel(slot.role, locale)}{count != null ? ` · ${count} ${locale === 'pl' ? 'zawodników' : 'players'}` : ''}{solved ? ` · ${answer.player_nickname}` : ''}</span>
              {slot.conditions.map((c) => <span key={c.id} className="block text-[12px] leading-relaxed" style={{ color: 'var(--text-dim)' }}>{locale === 'pl' ? c.label_pl : c.label_en}</span>)}
              {solved && <span className="block text-xs mt-1 tabular" style={{ color: 'var(--gold)' }}>{formatDeduction(answer.deduction ?? Math.max(0, -answer.points_awarded), locale)} {locale === 'pl' ? 'pkt' : 'pts'}</span>}
            </span>
            {solved ? <Check size={17} style={{ color: 'var(--ok)' }} aria-hidden /> : !disabled && <ChevronRight size={17} style={{ color: 'var(--text-faint)' }} aria-hidden />}
          </button>
        )
      })}
    </div>
  )
}
