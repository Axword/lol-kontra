'use client'
import { useId, type CSSProperties } from 'react'
import { Check, Plus } from 'lucide-react'
import { DailySlot, GameAnswer, Role } from '@/lib/api'
import { roleLabel } from '@/lib/flags'
import { rarityForPercent, rarityPalette } from '@/lib/rarity'
import RarityIndicator from './RarityIndicator'
import PlayerPortrait from './PlayerPortrait'
import { usePrefs } from '@/lib/store'

type Props = {
  slots: DailySlot[]
  answers: Record<number, GameAnswer>
  onPick: (slot: DailySlot) => void
  disabled?: boolean
  activeSlotId?: number | null
  inspect?: boolean
  candidateCounts?: Record<number, number>
  portraits?: Record<number, string | null | undefined>
}

const POSITIONS: Record<Role, { left: string; top: string }> = {
  top: { left: '20%', top: '20%' },
  jungle: { left: '25%', top: '53%' },
  mid: { left: '60%', top: '36%' },
  adc: { left: '81%', top: '67%' },
  support: { left: '51%', top: '84%' },
}

export default function RiftBoard({ slots, answers, onPick, disabled, activeSlotId, inspect = false, candidateCounts, portraits }: Props) {
  const locale = usePrefs((s) => s.locale)
  const boardId = useId()
  return (
    <div className="rift-surface" aria-label={locale === 'pl' ? 'Mapa Summoner’s Rift' : 'Summoner’s Rift map'}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/rift-map-dark.png" alt="" aria-hidden className="rift-map" draggable={false} />
      {slots.map((slot) => {
        const pos = POSITIONS[slot.role]
        if (!pos) return null
        const answer = answers[slot.id]
        const solved = answer?.is_correct === true
        const nodeState = solved ? 'solved' : answer ? 'wrong' : 'empty'
        const label = roleLabel(slot.role, locale)
        const count = candidateCounts?.[slot.id]
        const ariaLabel = `${label} – ${count != null ? `${count} ${locale === 'pl' ? 'pasujących zawodników' : 'matching players'}` : solved ? answer.player_nickname : locale === 'pl' ? 'puste' : 'empty'}`
        const rarity = solved ? (answer.is_diamond_pick ? 'diamond' : rarityForPercent(answer.rarity_percent)) : null
        const portrait = solved ? (portraits?.[answer.player] ?? answer.player_portrait_url) : null
        const roleIcon = <span className="rift-role-icon">
          {count != null ? <span className="text-lg font-semibold tabular">{count}</span> : <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/roles/${slot.role}.svg`} alt="" aria-hidden draggable={false} />
          </>}
        </span>
        const pick = () => { if (!disabled && (!solved || inspect)) onPick(slot) }
        return (
          <div key={slot.id} className="rift-position" style={{ '--left': pos.left, '--top': pos.top, zIndex: activeSlotId === slot.id ? 2 : 1 } as CSSProperties}>
            <button className="rift-card rarity-surface" data-state={nodeState} data-rarity={rarity ?? undefined} style={{ backgroundColor: rarity ? rarityPalette[rarity].background : undefined }} disabled={disabled || (solved && !inspect)} onClick={pick} aria-label={ariaLabel} aria-describedby={`${boardId}-${slot.id}`}>
              <span className="rift-card-head">
                {solved ? <PlayerPortrait url={portrait} fallback={roleIcon} /> : roleIcon}
                <span className="flex-1 min-w-0">
                  <span className="rift-role-name">{label}</span>
                  {solved && <span className="rift-player-name">{answer.player_nickname}</span>}
                </span>
                {solved ? <Check size={16} aria-hidden style={{ color: 'var(--ok)' }} /> : !disabled && <Plus size={15} aria-hidden className="opacity-60 shrink-0" />}
              </span>
              <ul className="rift-conditions" id={`${boardId}-${slot.id}`}>
                {slot.conditions.map((c) => <li key={c.id}>{locale === 'pl' ? c.label_pl : c.label_en}</li>)}
              </ul>
              {count != null && <div className="mt-3 text-xs tabular">{count} {locale === 'pl' ? 'zawodników' : 'players'}</div>}
              {solved && (
                <div className="rift-result">
                  <RarityIndicator percent={answer.rarity_percent} locale={locale} isDiamond={answer.is_diamond_pick} />
                </div>
              )}
            </button>
            <button className="rift-marker rarity-surface" data-state={nodeState} data-rarity={rarity ?? undefined} style={{ backgroundColor: rarity ? rarityPalette[rarity].background : undefined }} disabled={disabled || (solved && !inspect)} onClick={pick} aria-label={ariaLabel} aria-describedby={`${boardId}-${slot.id}`}>
              {count != null ? <strong aria-hidden className="tabular">{count}</strong> : solved ? <PlayerPortrait url={portrait} className="rift-player-portrait" fallback={<>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/roles/${slot.role}.svg`} alt="" aria-hidden draggable={false} />
              </>} /> : <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`/roles/${slot.role}.svg`} alt="" aria-hidden draggable={false} />
              </>}
              <span>{solved ? answer.player_nickname : label}</span>
              {solved && <RarityIndicator percent={answer.rarity_percent} locale={locale} isDiamond={answer.is_diamond_pick} className="text-[10px]" />}
            </button>
          </div>
        )
      })}
    </div>
  )
}
