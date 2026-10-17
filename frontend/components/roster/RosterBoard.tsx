'use client'
import { useState } from 'react'
import { Daily, DailySlot, MAX_ERRORS, verifyPick } from '@/lib/api'
import { rarityClass, rarityLabel, roleLabel } from '@/lib/flags'
import { useGame, useGameStore, usePrefs } from '@/lib/store'
import { sound } from '@/lib/sound'
import RiftBoard from './RiftBoard'
import PlayerPickerModal from './PlayerPickerModal'

type Flash = {
  correct: boolean
  nickname: string
  role: string
  tier: string | null
  percent: number
  deduction: number
  diamond: boolean
} | null

export default function RosterBoard({ daily }: { daily: Daily }) {
  const locale = usePrefs(s => s.locale)
  const game = useGame(daily.id)
  const applyPick = useGameStore(s => s.applyPick)
  const clearPick = useGameStore(s => s.clearPick)
  const resetGame = useGameStore(s => s.resetGame)

  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [flash, setFlash] = useState<Flash>(null)

  const picks = game.picks
  const gameOver = game.errors >= MAX_ERRORS
  const solved = daily.slots.filter(s => picks[s.id]?.is_correct).length
  const finished = game.finished || gameOver || solved >= daily.slots.length

  const openPicker = (slot: DailySlot) => {
    if (picks[slot.id]?.is_correct) return
    if (finished) return
    sound.open()
    setFlash(null)
    setPickerSlot(slot)
  }

  const handleSelect = (slot: DailySlot, slug: string, nickname: string) => {
    const result = verifyPick(slot, slug)
    applyPick(daily.id, {
      slotId: slot.id,
      playerSlug: slug,
      playerNickname: nickname,
      is_correct: result.is_correct,
      rarity_tier: result.rarity_tier,
      deduction: result.deduction,
      pick_percent: result.pick_percent,
      is_diamond_pick: result.is_diamond_pick,
      locked: result.is_correct,
    }, daily.slots.length, daily.date)

    if (result.is_correct) {
      result.is_diamond_pick ? sound.diamond() : sound.success()
      setPickerSlot(null)
    } else {
      sound.error()
    }

    setFlash({
      correct: result.is_correct,
      nickname,
      role: slot.role,
      tier: result.rarity_tier,
      percent: result.pick_percent,
      deduction: result.deduction,
      diamond: result.is_diamond_pick,
    })
  }

  if (!daily.slots?.length) {
    return (
      <div className="console text-center py-10 px-4 text-warn">
        {locale === 'pl' ? 'Ta zagadka nie ma slotów.' : 'This puzzle has no slots.'}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <RiftBoard
        slots={daily.slots}
        picks={picks}
        onPick={openPicker}
        onClear={slotId => clearPick(daily.id, slotId)}
        disabled={finished}
        activeSlotId={pickerSlot?.id ?? null}
      />

      {/*
        Jedna linia informacji zwrotnej po ruchu. Zastąpiła pasek statusu z
        sześcioma licznikami, siatkę "wyniki live" i legendę – wszystkie
        powtarzały to, co widać na mapie i w pasku górnym.
      */}
      <div className="min-h-[38px] flex items-center gap-3 flex-wrap">
        {flash ? (
          <div className="panel px-3 py-2 text-[13px] flex-1">
            {flash.correct ? (
              <span>
                <span className="eyebrow mr-2">{roleLabel(flash.role, locale)}</span>
                <b className="text-ink">{flash.nickname}</b>{' '}
                <span className="text-muted">{locale === 'pl' ? 'pasuje.' : 'fits.'}</span>{' '}
                <span className={flash.diamond ? 'r-diamond' : rarityClass[flash.tier || 'common']}>
                  {flash.diamond
                    ? (locale === 'pl' ? 'Najrzadszy poprawny wybór' : 'Rarest correct pick')
                    : rarityLabel(flash.tier, locale)}
                </span>
                <span className="mono text-muted">
                  {' · '}{flash.percent.toFixed(1)}%{' · '}
                </span>
                <span className="mono text-accent">−{flash.deduction}</span>
              </span>
            ) : (
              <span className="text-red">
                <span className="eyebrow mr-2">{roleLabel(flash.role, locale)}</span>
                <b>{flash.nickname}</b>{' '}
                {locale === 'pl' ? 'nie spełnia warunków.' : 'does not match.'}{' '}
                <span className="text-muted">
                  {locale === 'pl'
                    ? `Zostało żyć: ${Math.max(0, MAX_ERRORS - game.errors)}.`
                    : `Lives left: ${Math.max(0, MAX_ERRORS - game.errors)}.`}
                </span>
              </span>
            )}
          </div>
        ) : (
          <div className="text-[13px] text-muted flex-1">
            {finished
              ? (locale === 'pl' ? 'Gra zakończona.' : 'Game over.')
              : (locale === 'pl'
                  ? 'Kliknij pozycję na mapie albo kartę poniżej.'
                  : 'Click a position on the map or a card below.')}
          </div>
        )}

        <button
          onClick={() => {
            const q = locale === 'pl' ? 'Zacząć ten dzień od nowa?' : 'Restart this day?'
            if (confirm(q)) { resetGame(daily.id); setFlash(null) }
          }}
          className="btn btn-ghost text-[11px] px-2.5 py-1.5"
        >
          {locale === 'pl' ? 'Od nowa' : 'Restart'}
        </button>
      </div>

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        currentPick={pickerSlot ? picks[pickerSlot.id] : undefined}
        onSelect={(slug, nickname) => { if (pickerSlot) handleSelect(pickerSlot, slug, nickname) }}
        onClose={() => { sound.close(); setPickerSlot(null) }}
      />
    </div>
  )
}
