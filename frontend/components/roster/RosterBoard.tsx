'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Daily, DailySlot, GameAnswer, GameState, Player, formatApiError, useAnswerSlot, useAnswerStats } from '@/lib/api'
import { useGameDate } from '@/lib/daily'
import { usePrefs } from '@/lib/store'
import { sound } from '@/lib/sound'
import PlayerPickerModal from './PlayerPickerModal'
import RarityIndicator from './RarityIndicator'
import RiftBoard from './RiftBoard'
import SlotList from './SlotList'

type Props = {
  daily: Daily
  state: GameState
}

type Flash = {
  correct: boolean
  nickname: string
  percent: number | null
  provisional: boolean
} | null

export default function RosterBoard({ daily, state }: Props) {
  const locale = usePrefs((s) => s.locale)
  const guestToken = usePrefs((s) => s.guestToken)
  const ensureGuestToken = usePrefs((s) => s.ensureGuestToken)

  const [pickerSlot, setPickerSlot] = useState<DailySlot | null>(null)
  const [flash, setFlash] = useState<Flash>(null)
  const [error, setError] = useState<string | null>(null)
  const pending = useRef(false)
  const boardRef = useRef<HTMLDivElement>(null)
  const pickerWasOpen = useRef(false)

  const answer = useAnswerSlot(daily.id)
  const archived = daily.date < useGameDate()
  const shares = useAnswerStats(daily.id, archived)

  const answersBySlot = useMemo(() => {
    const map: Record<number, GameAnswer> = {}
    for (const a of state.answers) {
      const percent = shares.data?.results.find((row) => row.slot_id === a.daily_slot && row.player_slug === a.player_slug)?.pick_percent
      map[a.daily_slot] = archived && a.is_correct
        ? { ...a, rarity_percent: shares.data ? percent ?? 0 : null }
        : a
    }
    return map
  }, [state.answers, archived, shares.data])

  const over = state.is_over
  useEffect(() => {
    setPickerSlot(null)
    setFlash(null)
    setError(null)
  }, [daily.id])

  useEffect(() => {
    if (pickerSlot && (over || answersBySlot[pickerSlot.id]?.is_correct)) {
      setPickerSlot(null)
      setError(null)
    }
  }, [over, pickerSlot, answersBySlot])

  useEffect(() => {
    if (pickerSlot) {
      pickerWasOpen.current = true
    } else if (pickerWasOpen.current) {
      pickerWasOpen.current = false
      if (!over && document.activeElement === document.body) boardRef.current?.focus({ preventScroll: true })
    }
  }, [pickerSlot, over])

  const handleSelect = (player: Player) => {
    if (!pickerSlot || over || pending.current || answersBySlot[pickerSlot.id]?.is_correct) return
    pending.current = true
    setError(null)
    answer.mutate(
      {
        slot_id: pickerSlot.id,
        player_slug: player.slug,
        guest_token: guestToken || ensureGuestToken(),
      },
      {
        onSuccess: (data) => {
          if (data.is_correct) {
            sound.success()
            setPickerSlot(null)
          } else {
            sound.error()
            setError(locale === 'pl'
              ? `${data.player_nickname} nie spełnia warunków. Pozostało żyć: ${data.errors_left}.`
              : `${data.player_nickname} does not match. Lives left: ${data.errors_left}.`)
            // Slot zostaje otwarty – gracz może próbować dalej, dopóki ma życia.
            if (data.is_over) setPickerSlot(null)
          }
          setFlash({
            correct: data.is_correct,
            nickname: data.player_nickname,
            percent: data.pick_percent,
            provisional: data.is_provisional,
          })
        },
        onError: (e: any) => {
          sound.error()
          setError(formatApiError(e, locale === 'pl'
                ? 'Nie udało się wysłać odpowiedzi. Spróbuj ponownie.'
                : 'Could not submit the answer. Try again.'))
        },
        onSettled: () => { pending.current = false },
      }
    )
  }

  const openPicker = (slot: DailySlot) => {
    if (over || pending.current || answersBySlot[slot.id]?.is_correct) return
    setError(null)
    setFlash(null)
    sound.open()
    setPickerSlot(slot)
  }

  return (
    <div className="space-y-3">
      <div ref={boardRef} tabIndex={-1} role="group" aria-label={locale === 'pl' ? 'Pozycje' : 'Positions'}>
      <RiftBoard
        slots={daily.slots}
        answers={answersBySlot}
        onPick={openPicker}
        disabled={over}
        activeSlotId={pickerSlot?.id ?? null}
      />
      </div>

      {/* Komunikat po ruchu – jedna linia, znika przy kolejnym ruchu. */}
      {flash && !over && (
        <div
          role="status"
          aria-live="polite"
          className="panel-flat px-3 py-2 text-[13px] rise"
          style={{ borderColor: flash.correct ? 'var(--gold)' : 'var(--bad)' }}
        >
          {flash.correct ? (
            <span>
              <b>{flash.nickname}</b>{' '}
              <span style={{ color: 'var(--text-dim)' }}>
                {locale === 'pl' ? 'pasuje.' : 'fits.'}
              </span>{' '}
              {flash.percent != null && (
                <span>
                  {' · '}<RarityIndicator percent={flash.percent} locale={locale} />
                </span>
              )}
              {flash.provisional && (
                <span className="text-[11px]" style={{ color: 'var(--text-faint)' }}>
                  {' · '}
                  {locale === 'pl'
                    ? 'wynik wstępny'
                    : 'provisional score'}
                </span>
              )}
            </span>
          ) : (
            <span style={{ color: 'var(--bad)' }}>
              <b>{flash.nickname}</b>{' '}
              {locale === 'pl' ? 'nie spełnia warunków.' : 'does not match.'}{' '}
              <span style={{ color: 'var(--text-dim)' }}>
                {locale === 'pl'
                  ? `Pozostało żyć: ${state.errors_left}.`
                  : `Lives left: ${state.errors_left}.`}
              </span>
            </span>
          )}
        </div>
      )}

      {!over && <SlotList
        slots={daily.slots}
        answers={answersBySlot}
        onPick={openPicker}
        disabled={over}
      />}

      <PlayerPickerModal
        slot={pickerSlot}
        open={!!pickerSlot}
        busy={answer.isPending}
        error={error}
        onClose={() => { sound.close(); setPickerSlot(null); setError(null) }}
        onSelect={handleSelect}
      />
    </div>
  )
}
