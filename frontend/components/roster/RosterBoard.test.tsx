import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Daily, DailySlot, GameAnswer, GameState } from '@/lib/api'
import RosterBoard from './RosterBoard'

const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
  ensureGuestToken: vi.fn(() => 'guest-fixture'),
  shares: undefined as { results: { slot_id: number; player_slug: string; pick_percent: number }[] } | undefined,
  boardAnswers: {} as Record<number, GameAnswer>,
}))

vi.mock('@/lib/daily', () => ({ useGameDate: () => '2026-10-19' }))

vi.mock('@/lib/api', () => ({
  useAnswerSlot: () => ({ mutate: mocks.mutate, isPending: false }),
  useAnswerStats: () => ({ data: mocks.shares }),
  formatApiError: (_error: unknown, fallback: string) => fallback,
}))
vi.mock('@/lib/store', () => ({
  usePrefs: (select: (state: unknown) => unknown) => select({
    locale: 'pl', guestToken: 'guest-fixture', ensureGuestToken: mocks.ensureGuestToken,
  }),
}))
vi.mock('@/lib/sound', () => ({
  sound: { open: vi.fn(), close: vi.fn(), success: vi.fn(), error: vi.fn(), diamond: vi.fn() },
}))
vi.mock('./RiftBoard', () => ({
  default: ({ slots, answers, onPick }: { slots: DailySlot[]; answers: Record<number, GameAnswer>; onPick: (slot: DailySlot) => void }) => {
    mocks.boardAnswers = answers
    return <div>
    {slots.map((slot) => <button key={slot.id} onClick={() => onPick(slot)}>{slot.label_pl}</button>)}
    </div>
  },
}))
vi.mock('./SlotList', () => ({ default: () => null }))
vi.mock('./PlayerPickerModal', () => ({
  default: ({ open, slot }: { open: boolean; slot: DailySlot | null }) => open && slot
    ? <div role="dialog" aria-label={slot.label_pl} />
    : null,
}))

const daily: Daily = {
  id: 7, date: '2026-10-17', status: 'published', slots: [
    { id: 11, position: 1, role: 'top', label_pl: 'Top', label_en: 'Top', conditions: [] },
    { id: 12, position: 2, role: 'jungle', label_pl: 'Dżungla', label_en: 'Jungle', conditions: [] },
  ],
}

const initialState: GameState = {
  id: 1, daily: 7, total_points: 0, is_scored: false, is_practice: false,
  errors_used: 0, errors_left: 10, max_errors: 10, slots_total: 2,
  correct_count: 0, is_over: false, answers: [],
}

function answer(slotId: number, correct: boolean): GameAnswer {
  return {
    id: slotId, daily_slot: slotId, slot_role: slotId === 11 ? 'top' : 'jungle',
    player: 101, player_nickname: 'Player fixture', player_slug: 'player-fixture',
    is_correct: correct, rarity_tier: correct ? 'common' : null,
    rarity_percent: correct ? 100 : null, points_awarded: correct ? 10 : 0,
    is_diamond_pick: false,
  }
}

afterEach(() => { cleanup(); mocks.shares = undefined; mocks.boardAnswers = {} })

describe('picker follows external game updates', () => {
  it('closes an open picker when another window finishes the game', () => {
    const view = render(<RosterBoard daily={daily} state={initialState} />)
    fireEvent.click(screen.getByRole('button', { name: 'Top' }))
    expect(screen.getByRole('dialog', { name: 'Top' })).toBeTruthy()

    view.rerender(<RosterBoard daily={daily} state={{
      ...initialState, is_over: true, errors_used: 10, errors_left: 0,
    }} />)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('closes an open picker when another window solves its slot', () => {
    const view = render(<RosterBoard daily={daily} state={initialState} />)
    fireEvent.click(screen.getByRole('button', { name: 'Top' }))
    expect(screen.getByRole('dialog', { name: 'Top' })).toBeTruthy()

    view.rerender(<RosterBoard daily={daily} state={{
      ...initialState, answers: [answer(11, true)], correct_count: 1, total_points: 10,
    }} />)

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('shows current real percentages on a saved unfinished board without changing its score or answers', () => {
    mocks.shares = { results: [{ slot_id: 11, player_slug: 'player-fixture', pick_percent: 25 }] }
    const saved = { ...initialState, total_points: 458.3, answers: [{ ...answer(11, true), rarity_percent: 41.7 }] }
    const snapshot = JSON.stringify(saved)
    render(<RosterBoard daily={daily} state={saved} />)
    expect(mocks.boardAnswers[11].rarity_percent).toBe(25)
    expect(JSON.stringify(saved)).toBe(snapshot)
  })

  it.each([
    ['a miss on the selected slot', { answers: [answer(11, false)], errors_used: 1, errors_left: 9 }],
    ['a miss on another slot', { answers: [answer(12, false)], errors_used: 1, errors_left: 9 }],
    ['a correct answer on another slot', { answers: [answer(12, true)], correct_count: 1, total_points: 10 }],
  ] satisfies [string, Partial<GameState>][] )('keeps the picker open after %s', (_change, update) => {
    const view = render(<RosterBoard daily={daily} state={initialState} />)
    fireEvent.click(screen.getByRole('button', { name: 'Top' }))

    view.rerender(<RosterBoard daily={daily} state={{ ...initialState, ...update }} />)

    expect(screen.getByRole('dialog', { name: 'Top' })).toBeTruthy()
    expect(mocks.mutate).not.toHaveBeenCalled()
  })
})
